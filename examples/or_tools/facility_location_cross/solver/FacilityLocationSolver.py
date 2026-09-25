"""Alternate fixed-opening recourse and a capacity-priced dual model."""

from copy import deepcopy
from fractions import Fraction
from math import ceil, isfinite
from time import monotonic

from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

from ..cotwin import CotFacilityLocation
from .DualMaster import DualMaster
from .ExactClosure import ExactClosure
from .FacilityLocationSolution import FacilityLocationSolution
from .FixedOpeningSubproblem import FixedOpeningSubproblem
from .PricedSubproblem import PriceVector, PricedSubproblem
from .ScoreNoImprovement import ScoreNoImprovement


class FacilityLocationSolver:
    def __init__(
        self,
        workers: int = 10,
        no_improvement_seconds: float = 15,
        time_limit: float | None = None,
    ) -> None:
        if type(workers) is not int or workers < 1:
            raise ValueError("workers must be a positive integer")
        for name, value in (
            ("no_improvement_seconds", no_improvement_seconds),
            ("time_limit", time_limit),
        ):
            if value is None and name == "time_limit":
                continue
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        self.workers = workers
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit

    def solve(self, cotwin: CotFacilityLocation) -> FacilityLocationSolution:
        started = monotonic()
        total_deadline = (
            float("inf") if self.time_limit is None else started + self.time_limit
        )
        logger = ScoreNoImprovement(started, self.no_improvement_seconds)
        master = DualMaster(cotwin)
        fixed = FixedOpeningSubproblem(cotwin)
        priced = PricedSubproblem(cotwin)
        iterations = 0
        primal_solves = 0
        pricing_solves = 0
        lower_bound: int | None = None
        reason = "cross_stalled"

        if not cotwin.domain.consumers:
            logger.record((0, 0), {})
            return self._result(
                cotwin,
                logger,
                started,
                "OPTIMAL",
                "optimal",
                iterations=0,
                primal_solves=0,
                pricing_solves=0,
                dual_master_solves=0,
                columns=0,
                lower_bound=0,
            )

        if cotwin.use_greedy_seed:
            seed = self._greedy_seed(cotwin)
            if seed is not None:
                self._record(cotwin, logger, seed)
                master.add_pattern(seed)

        try:
            prices = priced.checked_prices({})
        except ValueError:
            prices = None
            reason = "pricing_unavailable"
        phase = "cost"
        from_master = False
        while (
            prices is not None
            and self._cross_remaining(logger, total_deadline, started) > 0
        ):
            budget = min(2.0, self._cross_remaining(logger, total_deadline, started))
            result = priced.solve(
                prices,
                phase,
                budget,
                self.workers,
                lambda assignment: self._record(cotwin, logger, assignment),
            )
            pricing_solves += 1
            iterations += 1
            if result.assignment is None:
                reason = "pricing_unresolved"
                break
            self._record(cotwin, logger, result.assignment)
            new_pattern = master.add_pattern(result.assignment)
            if result.lower_bound is not None:
                bound = ceil(result.lower_bound)
                lower_bound = bound if lower_bound is None else max(lower_bound, bound)
                if logger.best_score is not None:
                    upper = self._weighted(cotwin, logger.best_score)
                    if lower_bound > upper:
                        raise RuntimeError(
                            "Lagrangian lower bound exceeds replayed score"
                        )
                    if lower_bound == upper:
                        reason = "dual_bound_closed"
                        break

            opened = set(result.assignment.values())
            lp_prices: dict[int, Fraction] | None = None
            if self._cross_remaining(logger, total_deadline, started) > 0:
                lp = fixed.solve_lp(
                    opened,
                    min(2.0, self._cross_remaining(logger, total_deadline, started)),
                )
                primal_solves += 1
                if lp.status == pywraplp.Solver.OPTIMAL:
                    lp_prices = lp.capacity_prices
                    exact_assignment = self._integral_lp_assignment(cotwin, lp, opened)
                else:
                    exact_assignment = None
                if exact_assignment is not None:
                    self._record(cotwin, logger, exact_assignment)
                    new_pattern |= master.add_pattern(exact_assignment)
                elif (
                    lp.status != pywraplp.Solver.INFEASIBLE
                    and self._cross_remaining(logger, total_deadline, started) > 0
                ):
                    _, assignment, _ = fixed.solve_integer(
                        opened,
                        min(
                            2.0, self._cross_remaining(logger, total_deadline, started)
                        ),
                        self.workers,
                        lambda item: self._record(cotwin, logger, item),
                    )
                    if assignment is not None:
                        self._record(cotwin, logger, assignment)
                        new_pattern |= master.add_pattern(assignment)

            if self._cross_remaining(logger, total_deadline, started) <= 0:
                break
            master_result = master.solve(
                min(0.5, self._cross_remaining(logger, total_deadline, started))
            )
            if from_master and not new_pattern:
                reason = "cross_stalled"
                break
            if master_result is None and lp_prices is None:
                reason = "master_unresolved"
                break
            use_master = master_result is not None and (
                iterations % 2 == 0 or lp_prices is None or not new_pattern
            )
            next_phase = master_result.phase if use_master else "cost"
            try:
                next_prices = priced.checked_prices(
                    master_result.prices if use_master else lp_prices
                )
            except ValueError:
                reason = "pricing_unavailable"
                break
            if not new_pattern and self._price_key(
                next_prices, next_phase
            ) == self._price_key(prices, phase):
                reason = "cross_stalled"
                break
            prices, phase, from_master = next_prices, next_phase, use_master

        if reason == "dual_bound_closed":
            return self._result(
                cotwin,
                logger,
                started,
                "OPTIMAL",
                reason,
                iterations=iterations,
                primal_solves=primal_solves,
                pricing_solves=pricing_solves,
                dual_master_solves=master.solves,
                columns=len(master.patterns),
                lower_bound=lower_bound,
            )

        closure = ExactClosure(cotwin)
        first_closure_solve = True
        while self._remaining(logger, total_deadline) > 0:
            prior_best = logger.best_score
            cutoff = (
                None
                if first_closure_solve or prior_best is None
                else self._weighted(cotwin, prior_best) - 1
            )
            status, assignment = closure.solve(
                min(5.0, self._remaining(logger, total_deadline)),
                self.workers,
                lambda item: self._record(cotwin, logger, item),
                hint=logger.best_assignments if cutoff is None else None,
                cutoff=cutoff,
            )
            first_closure_solve = False
            if assignment is not None:
                self._record(cotwin, logger, assignment)
            if status == cp_model.OPTIMAL:
                if logger.best_score is None:
                    raise RuntimeError(
                        "Exact closure proved an optimum without a solution"
                    )
                lower_bound = self._weighted(cotwin, logger.best_score)
                reason = "optimal"
                break
            if status == cp_model.INFEASIBLE:
                if cutoff is None:
                    if logger.best_score is not None:
                        raise RuntimeError(
                            "Exact closure excluded a replayed incumbent"
                        )
                    reason = "infeasible"
                else:
                    lower_bound = self._weighted(cotwin, logger.best_score)
                    reason = "optimal"
                break

        if reason == "optimal":
            status_name = "OPTIMAL"
        elif reason == "infeasible":
            status_name = "INFEASIBLE"
            lower_bound = None
        elif logger.best_score is not None:
            status_name = "FEASIBLE"
        else:
            status_name = "UNKNOWN"
        if (
            status_name in ("FEASIBLE", "UNKNOWN")
            and self._remaining(logger, total_deadline) <= 0
        ):
            reason = self._deadline_reason(logger, total_deadline)
        return self._result(
            cotwin,
            logger,
            started,
            status_name,
            reason,
            iterations=iterations,
            primal_solves=primal_solves,
            pricing_solves=pricing_solves,
            dual_master_solves=master.solves,
            columns=len(master.patterns),
            lower_bound=lower_bound,
        )

    @staticmethod
    def _price_key(prices: PriceVector, phase: str) -> tuple:
        return phase, tuple(prices.fractions().items())

    def _cross_remaining(
        self, logger: ScoreNoImprovement, total_deadline: float, started: float
    ) -> float:
        idle_reserve = 0.3 * self.no_improvement_seconds
        total_reserve = 0 if self.time_limit is None else 0.3 * self.time_limit
        return max(
            0.0,
            min(logger.deadline - idle_reserve, total_deadline - total_reserve)
            - monotonic(),
        )

    @staticmethod
    def _remaining(logger: ScoreNoImprovement, total_deadline: float) -> float:
        return max(0.0, min(logger.deadline, total_deadline) - monotonic())

    @staticmethod
    def _deadline_reason(logger: ScoreNoImprovement, total_deadline: float) -> str:
        return "time_limit" if total_deadline <= logger.deadline else "no_improvement"

    @staticmethod
    def _weighted(cotwin: CotFacilityLocation, score: tuple[int, int]) -> int:
        return cotwin.hard_weight * score[0] + score[1]

    @staticmethod
    def _record(
        cotwin: CotFacilityLocation,
        logger: ScoreNoImprovement,
        assignment: dict[int, int],
    ) -> bool:
        domain = deepcopy(cotwin.domain)
        if set(assignment) != {c.id for c in domain.consumers}:
            raise ValueError("Incomplete assignment")
        facilities = {f.id: f for f in domain.facilities}
        if any(fid not in facilities for fid in assignment.values()):
            raise ValueError("Unknown facility in assignment")
        for consumer in domain.consumers:
            consumer.facility = facilities[assignment[consumer.id]]
        metrics = domain.calculate_metrics()
        score = metrics["hard_penalty"], metrics["soft_cost"]
        if cotwin.mode == "strict" and score[0]:
            return False
        return logger.record(score, assignment)

    @staticmethod
    def _integral_lp_assignment(cotwin, lp, opened):
        if lp.assignments is None or lp.cut is None:
            return None
        assignment = lp.assignments
        if set(assignment.values()) != opened:
            return None
        domain = deepcopy(cotwin.domain)
        facilities = {f.id: f for f in domain.facilities}
        for consumer in domain.consumers:
            consumer.facility = facilities[assignment[consumer.id]]
        metrics = domain.calculate_metrics()
        if cotwin.mode == "strict" and metrics["hard_penalty"]:
            return None
        cost = (
            cotwin.hard_weight * metrics["hard_penalty"]
            + 5 * metrics["total_distance_m"]
        )
        return assignment if lp.cut.value(opened) == cost else None

    @staticmethod
    def _greedy_seed(cotwin: CotFacilityLocation) -> dict[int, int] | None:
        domain = cotwin.domain
        loads = {f.id: 0 for f in domain.facilities}
        opened: set[int] = set()
        assignments = {}
        for consumer in domain.consumers:
            candidates = domain.facilities
            if cotwin.mode == "strict":
                candidates = [
                    f for f in candidates if loads[f.id] + consumer.demand <= f.capacity
                ]
                if not candidates:
                    return None

            def incremental_cost(facility):
                fid = facility.id
                old = max(0, loads[fid] - facility.capacity)
                new = max(0, loads[fid] + consumer.demand - facility.capacity)
                return (
                    cotwin.hard_weight * (new - old)
                    + 5 * cotwin.distances[consumer.id, fid]
                    + (2 * facility.setup_cost if fid not in opened else 0),
                    fid,
                )

            selected = min(candidates, key=incremental_cost)
            assignments[consumer.id] = selected.id
            loads[selected.id] += consumer.demand
            opened.add(selected.id)
        return assignments

    @staticmethod
    def _result(
        cotwin,
        logger,
        started,
        status,
        reason,
        *,
        iterations,
        primal_solves,
        pricing_solves,
        dual_master_solves,
        columns,
        lower_bound=None,
    ) -> FacilityLocationSolution:
        return FacilityLocationSolution(
            status=status,
            assignments=logger.best_assignments,
            hard_penalty=None if logger.best_score is None else logger.best_score[0],
            soft_cost=None if logger.best_score is None else logger.best_score[1],
            elapsed_seconds=monotonic() - started,
            termination_reason=reason,
            mode=cotwin.mode,
            iterations=iterations,
            primal_solves=primal_solves,
            pricing_solves=pricing_solves,
            dual_master_solves=dual_master_solves,
            columns=columns,
            lower_bound=lower_bound,
        )
