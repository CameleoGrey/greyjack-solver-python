"""Exact Benders search over facility openings and assignment recourse."""

from copy import deepcopy
from math import isfinite, lcm
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin import CotFacilityLocation
from .AssignmentSubproblem import AssignmentSubproblem, DualCut
from .FacilityLocationSolution import FacilityLocationSolution
from .ScoreNoImprovement import ScoreNoImprovement


class _IntegerIncumbent(cp_model.CpSolverSolutionCallback):
    def __init__(self, variables, consumers, record):
        super().__init__()
        self.variables = variables
        self.consumers = consumers
        self.record = record

    def on_solution_callback(self) -> None:
        assignments = {
            cid: next(
                fid
                for fid, variable in self.variables[cid].items()
                if self.value(variable)
            )
            for cid in self.consumers
        }
        self.record(assignments)


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
        validation_error = cotwin.master.validate()
        if validation_error:
            raise ValueError(f"Invalid Benders master: {validation_error}")
        started = monotonic()
        deadline = (
            float("inf") if self.time_limit is None else started + self.time_limit
        )
        logger = ScoreNoImprovement(started, self.no_improvement_seconds)
        master = cotwin.master.clone()
        openings = {
            fid: master.get_bool_var_from_proto_index(variable.index)
            for fid, variable in cotwin.openings.items()
        }
        theta = master.get_int_var_from_proto_index(cotwin.assignment_cost.index)
        lp = AssignmentSubproblem(cotwin)
        cut_keys: set[tuple] = set()
        iterations = 0
        optimality_cuts = 0
        feasibility_cuts = 0
        lower_bound = None
        reason = "search_stopped"

        if cotwin.use_greedy_seed and self._remaining(logger, deadline) > 0:
            seed = self._greedy_seed(cotwin)
            if seed is not None:
                self._record(cotwin, logger, seed, set(seed.values()))

        while self._remaining(logger, deadline) > 0:
            master_solver = self._new_solver(self._remaining(logger, deadline))
            status = master_solver.solve(master)
            if status == cp_model.INFEASIBLE:
                if logger.best_score is not None:
                    raise RuntimeError("Benders master excluded a valid incumbent")
                reason = "infeasible"
                break
            if status == cp_model.MODEL_INVALID:
                raise ValueError(f"Invalid Benders master: {master.validate()}")
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                reason = "master_unresolved"
                break

            opened = {
                fid
                for fid, variable in openings.items()
                if master_solver.value(variable)
            }
            master_value = master_solver.value(theta) + sum(
                2 * facility.setup_cost
                for facility in cotwin.domain.facilities
                if facility.id in opened
            )
            if status == cp_model.OPTIMAL:
                lower_bound = master_value
                if logger.best_score is not None and master_value >= self._weighted(
                    cotwin, logger.best_score
                ):
                    reason = "optimal"
                    break

            iterations += 1
            lp_result = lp.solve(opened, self._remaining(logger, deadline))
            if lp_result.cut is not None and self._add_dual_cut(
                master, theta, openings, cotwin, lp_result.cut, cut_keys
            ):
                optimality_cuts += 1

            exact_assignment = None
            exact_cost = None
            if lp_result.assignments is not None and lp_result.cut is not None:
                try:
                    score, distance = self._replay(
                        cotwin, lp_result.assignments, opened
                    )
                    candidate_cost = cotwin.hard_weight * score[0] + 5 * distance
                    if lp_result.cut.value(opened) == candidate_cost:
                        exact_assignment = lp_result.assignments
                        exact_cost = candidate_cost
                except ValueError:
                    pass

            if exact_assignment is None:
                if self._remaining(logger, deadline) <= 0:
                    reason = self._deadline_reason(logger, deadline)
                    break
                integer_status, exact_assignment, exact_cost = self._solve_integer(
                    cotwin,
                    opened,
                    logger,
                    self._remaining(logger, deadline),
                )
                if integer_status == cp_model.INFEASIBLE:
                    self._add_no_good(master, openings, opened)
                    feasibility_cuts += 1
                    continue
                if integer_status == cp_model.MODEL_INVALID:
                    raise ValueError("Invalid assignment subproblem")
                if integer_status != cp_model.OPTIMAL:
                    reason = "subproblem_unresolved"
                    break

            self._record(cotwin, logger, exact_assignment, opened)
            self._add_pattern_cost(master, theta, openings, opened, exact_cost)
            optimality_cuts += 1

        if (
            reason not in ("optimal", "infeasible")
            and self._remaining(logger, deadline) <= 0
        ):
            reason = self._deadline_reason(logger, deadline)
        if reason == "optimal":
            status_name = "OPTIMAL"
        elif reason == "infeasible":
            status_name = "INFEASIBLE"
        elif logger.best_assignments is not None:
            status_name = "FEASIBLE"
        else:
            status_name = "UNKNOWN"
        return FacilityLocationSolution(
            status_name,
            logger.best_assignments,
            None if logger.best_score is None else logger.best_score[0],
            None if logger.best_score is None else logger.best_score[1],
            monotonic() - started,
            reason,
            cotwin.mode,
            iterations,
            optimality_cuts,
            feasibility_cuts,
            lower_bound,
        )

    def _new_solver(self, seconds: float) -> cp_model.CpSolver:
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = max(0.001, seconds)
        return solver

    @staticmethod
    def _remaining(logger: ScoreNoImprovement, deadline: float) -> float:
        return max(0.0, min(logger.deadline, deadline) - monotonic())

    @staticmethod
    def _deadline_reason(logger: ScoreNoImprovement, deadline: float) -> str:
        return "time_limit" if deadline <= logger.deadline else "no_improvement"

    @staticmethod
    def _weighted(cotwin: CotFacilityLocation, score: tuple[int, int]) -> int:
        return cotwin.hard_weight * score[0] + score[1]

    @staticmethod
    def _replay(
        cotwin: CotFacilityLocation,
        assignments: dict[int, int],
        opened: set[int],
    ) -> tuple[tuple[int, int], int]:
        domain = deepcopy(cotwin.domain)
        facilities = {facility.id: facility for facility in domain.facilities}
        if set(assignments) != {consumer.id for consumer in domain.consumers}:
            raise ValueError("Incomplete assignment")
        if any(fid not in facilities for fid in assignments.values()):
            raise ValueError("Unknown facility in assignment")
        if set(assignments.values()) != opened:
            raise ValueError("Opening pattern differs from business facility usage")
        for consumer in domain.consumers:
            consumer.facility = facilities[assignments[consumer.id]]
        metrics = domain.calculate_metrics()
        if cotwin.mode == "strict" and metrics["hard_penalty"]:
            raise ValueError("Strict assignment exceeds capacity")
        return (metrics["hard_penalty"], metrics["soft_cost"]), metrics[
            "total_distance_m"
        ]

    def _record(
        self,
        cotwin: CotFacilityLocation,
        logger: ScoreNoImprovement,
        assignments: dict[int, int],
        opened: set[int],
    ) -> None:
        score, _ = self._replay(cotwin, assignments, opened)
        logger.record(score, assignments)

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

    def _solve_integer(
        self,
        cotwin: CotFacilityLocation,
        opened: set[int],
        logger: ScoreNoImprovement,
        seconds: float,
    ) -> tuple[int, dict[int, int] | None, int | None]:
        model, variables = self._build_integer_model(cotwin, opened)

        def record(assignments):
            self._record(cotwin, logger, assignments, opened)

        callback = _IntegerIncumbent(
            variables, (c.id for c in cotwin.domain.consumers), record
        )
        solver = self._new_solver(seconds)
        status = solver.solve(model, callback)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return status, None, None
        assignments = {
            cid: next(fid for fid, variable in row.items() if solver.value(variable))
            for cid, row in variables.items()
        }
        score, distance = self._replay(cotwin, assignments, opened)
        return status, assignments, cotwin.hard_weight * score[0] + 5 * distance

    @staticmethod
    def _build_integer_model(
        cotwin: CotFacilityLocation, opened: set[int]
    ) -> tuple[cp_model.CpModel, dict[int, dict[int, cp_model.IntVar]]]:
        """Build exact assignment recourse for one opening pattern."""
        model = cp_model.CpModel()
        facilities = [f for f in cotwin.domain.facilities if f.id in opened]
        variables = {}
        for consumer in cotwin.domain.consumers:
            row = {
                f.id: model.new_bool_var(f"assign_{consumer.id}_{f.id}")
                for f in facilities
            }
            model.add_exactly_one(row.values())
            variables[consumer.id] = row

        objective_terms = []
        for facility in facilities:
            fid = facility.id
            column = [variables[c.id][fid] for c in cotwin.domain.consumers]
            model.add(sum(column) >= 1)
            load = sum(c.demand * variables[c.id][fid] for c in cotwin.domain.consumers)
            if cotwin.mode == "strict":
                model.add(load <= facility.capacity)
            else:
                overload = model.new_int_var(
                    0,
                    max(
                        0,
                        sum(c.demand for c in cotwin.domain.consumers)
                        - facility.capacity,
                    ),
                    f"overload_{fid}",
                )
                model.add(overload >= load - facility.capacity)
                objective_terms.append(cotwin.hard_weight * overload)
        objective_terms.extend(
            5 * cotwin.distances[c.id, f.id] * variables[c.id][f.id]
            for c in cotwin.domain.consumers
            for f in facilities
        )
        model.minimize(sum(objective_terms))
        return model, variables

    @staticmethod
    def _add_no_good(master, openings, opened: set[int]) -> None:
        master.add_bool_or(
            [
                ~variable if fid in opened else variable
                for fid, variable in openings.items()
            ]
        )

    @staticmethod
    def _add_pattern_cost(master, theta, openings, opened: set[int], cost: int) -> None:
        pattern = [
            variable if fid in opened else ~variable
            for fid, variable in openings.items()
        ]
        master.add(theta >= cost).only_enforce_if(pattern)

    @staticmethod
    def _add_dual_cut(
        master,
        theta,
        openings,
        cotwin: CotFacilityLocation,
        cut: DualCut,
        seen: set[tuple],
    ) -> bool:
        scale = lcm(
            cut.intercept.denominator,
            *(coefficient.denominator for coefficient in cut.coefficients.values()),
        )
        intercept = int(scale * cut.intercept)
        coefficients = {fid: int(scale * cut.coefficients[fid]) for fid in openings}
        safe_bound = cp_model.INT_MAX // 2
        if (
            scale * cotwin.assignment_upper
            + abs(intercept)
            + sum(abs(value) for value in coefficients.values())
            > safe_bound
        ):
            return False
        key = (scale, intercept, tuple(coefficients.items()))
        if key in seen:
            return False
        seen.add(key)
        master.add(
            scale * theta
            >= intercept + sum(coefficients[fid] * openings[fid] for fid in openings)
        )
        return True
