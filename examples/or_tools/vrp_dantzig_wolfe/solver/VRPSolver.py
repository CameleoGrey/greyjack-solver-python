"""Root LP column generation followed by a restricted integer master."""

from math import isfinite
from time import monotonic
from typing import Callable

from ortools.linear_solver import pywraplp

from ..cotwin import CotVRP
from ..persistence.DomainBuilder import DomainBuilder
from .BestSolutionLogger import BestSolutionLogger
from .FastPricingSolver import FastPricingSolver
from .PricingSolver import PricingSolver
from .RoutePoolGenerator import RoutePoolGenerator
from .SeedSolver import SeedSolver
from .VRPSolution import VRPSolution


EPSILON = 1e-6


class VRPSolver:
    def __init__(
        self,
        *,
        time_limit: float = 30,
        seed_time_limit: float = 10,
        workers: int = 1,
        use_seed: bool = True,
        pricing_mode: str = "fast",
    ):
        for name, value in (
            ("time_limit", time_limit),
            ("seed_time_limit", seed_time_limit),
        ):
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        if type(workers) is not int or workers < 1:
            raise ValueError("workers must be a positive integer")
        if pricing_mode not in ("fast", "exact"):
            raise ValueError("pricing_mode must be 'fast' or 'exact'")
        self.time_limit = time_limit
        self.seed_time_limit = seed_time_limit
        self.workers = workers
        self.use_seed = use_seed
        self.pricing_mode = pricing_mode

    def solve(self, cotwin: CotVRP) -> VRPSolution:
        started = monotonic()
        best_logger = BestSolutionLogger(started)
        deadline = started + self.time_limit
        reserve = min(2.0, 0.2 * self.time_limit)
        cg_deadline = deadline - reserve
        groups_by_vehicle = {
            vehicle: group_index
            for group_index, group in enumerate(cotwin.groups)
            for vehicle in group.vehicle_indices
        }
        if not cotwin.customer_ids:
            empty = tuple(() for _ in cotwin.domain.vehicles)
            best_logger.record((0, 0, 0))
            return self._result(
                cotwin,
                empty,
                started,
                "FEASIBLE",
                "empty_instance",
                lp_converged=True,
                pricing_mode=self.pricing_mode,
            )

        generator_started = monotonic()
        seed_routes = None
        generator_score = None
        seed_proved_infeasible = False
        if self.use_seed:
            greedy = SeedSolver.greedy(cotwin)
            if cotwin.mode == "penalized" or SeedSolver._strict_valid(cotwin, greedy):
                seed_routes = greedy
                generator_score = self._score_routes(cotwin, greedy, groups_by_vehicle)
                self._add_seed_columns(cotwin, greedy, groups_by_vehicle)
                best_logger.record(generator_score)
            per_strategy = (
                min(0.05, self.time_limit / 10)
                if len(cotwin.customer_ids) < 10
                else min(10.0, self.time_limit / 3)
            )
            for strategy in RoutePoolGenerator.STRATEGIES:
                remaining = cg_deadline - monotonic()
                if remaining <= 0:
                    break
                pool = RoutePoolGenerator.generate(
                    cotwin,
                    min(per_strategy, remaining),
                    strategy,
                    on_solution=best_logger.record,
                )
                if pool.best_routes is not None and (
                    generator_score is None or pool.best_score < generator_score
                ):
                    seed_routes = pool.best_routes
                    generator_score = pool.best_score
            if seed_routes is None:
                seed_budget = min(
                    self.seed_time_limit,
                    max(0.0, cg_deadline - monotonic()),
                )
                seed_routes, seed_proved_infeasible = SeedSolver().solve(
                    cotwin,
                    seed_budget,
                    self.workers,
                    on_solution=best_logger.record,
                )
                if seed_routes is not None:
                    generator_score = self._score_routes(
                        cotwin, seed_routes, groups_by_vehicle
                    )
                    self._add_seed_columns(cotwin, seed_routes, groups_by_vehicle)
        generator_seconds = monotonic() - generator_started
        if seed_proved_infeasible:
            return self._result(
                cotwin,
                None,
                started,
                "INFEASIBLE",
                "seed_proved_infeasible",
                pricing_mode=self.pricing_mode,
                generator_seconds=generator_seconds,
            )

        master_seconds = 0.0
        pool_master_score = None
        best_routes = seed_routes
        if seed_routes is not None and monotonic() < cg_deadline:
            pool_master_started = monotonic()
            pool_routes, pool_status = self._solve_integer_master(
                cotwin,
                min(cg_deadline, pool_master_started + 1.0),
                seed_routes,
                on_solution=best_logger.record,
            )
            master_seconds += monotonic() - pool_master_started
            if pool_routes is not None and (
                best_routes is None
                or self._score_routes(cotwin, pool_routes, groups_by_vehicle)
                < self._score_routes(cotwin, best_routes, groups_by_vehicle)
            ):
                best_routes = pool_routes
            if pool_status in ("FEASIBLE", "OPTIMAL"):
                pool_master_score = self._score_routes(
                    cotwin, best_routes, groups_by_vehicle
                )

        pricing_started = monotonic()
        phases = (
            ("distance",) if cotwin.mode == "strict" else ("hard", "medium", "distance")
        )
        prior_lp_bounds: dict[str, float] = {}
        lp_converged = False
        pricing_status = "NOT_RUN"
        proved_infeasible = False
        if seed_routes is None:
            finished, value, pricing_status = self._generate(
                cotwin, "artificial", {}, cg_deadline
            )
            if finished and value is not None and value > EPSILON:
                proved_infeasible = True
            if not finished or value is None or value > EPSILON:
                phases = ()
        if proved_infeasible:
            return self._result(
                cotwin,
                None,
                started,
                "INFEASIBLE",
                "phase_one_proved_infeasible",
                pricing_mode=self.pricing_mode,
                pricing_status=pricing_status,
                generator_score=generator_score,
                pool_master_score=pool_master_score,
                generator_seconds=generator_seconds,
                pricing_seconds=monotonic() - pricing_started,
                master_seconds=master_seconds,
            )
        for phase in phases:
            if monotonic() >= cg_deadline:
                pricing_status = "TIME_LIMIT"
                break
            finished, value, pricing_status = self._generate(
                cotwin,
                phase,
                prior_lp_bounds if self.pricing_mode == "exact" else {},
                cg_deadline,
            )
            if self.pricing_mode == "exact":
                if not finished or value is None:
                    break
                prior_lp_bounds[phase] = value + EPSILON
        else:
            lp_converged = bool(phases) and self.pricing_mode == "exact"
        pricing_seconds = monotonic() - pricing_started

        final_master_started = monotonic()
        master_routes, master_status = self._solve_integer_master(
            cotwin, deadline, best_routes, on_solution=best_logger.record
        )
        master_seconds += monotonic() - final_master_started
        if master_routes is not None and (
            best_routes is None
            or self._score_routes(cotwin, master_routes, groups_by_vehicle)
            < self._score_routes(cotwin, best_routes, groups_by_vehicle)
        ):
            best_routes = master_routes
        if best_routes is None:
            return self._result(
                cotwin,
                None,
                started,
                "UNKNOWN",
                "time_limit" if monotonic() >= deadline else "no_integer_incumbent",
                lp_converged,
                master_status,
                pricing_status,
                pricing_mode=self.pricing_mode,
                generator_score=generator_score,
                pool_master_score=pool_master_score,
                generator_seconds=generator_seconds,
                pricing_seconds=pricing_seconds,
                master_seconds=master_seconds,
            )
        reason = (
            "time_limit"
            if monotonic() >= deadline
            else "pricing_budget_exhausted"
            if pricing_status == "TIME_LIMIT"
            else "pricing_converged"
            if lp_converged
            else "heuristic_complete"
            if self.pricing_mode == "fast"
            else "pricing_incomplete"
        )
        result = self._result(
            cotwin,
            best_routes,
            started,
            "FEASIBLE",
            reason,
            lp_converged,
            master_status,
            pricing_status,
            pricing_mode=self.pricing_mode,
            generator_score=generator_score,
            pool_master_score=pool_master_score,
            generator_seconds=generator_seconds,
            pricing_seconds=pricing_seconds,
            master_seconds=master_seconds,
        )
        # The business model independently recalculates all three score components.
        DomainBuilder("unused").build_from_solution(result, cotwin.domain)
        return result

    @staticmethod
    def _add_seed_columns(
        cotwin: CotVRP,
        routes: tuple[tuple[int, ...], ...],
        groups_by_vehicle: dict[int, int],
    ) -> None:
        if len(routes) != len(cotwin.domain.vehicles):
            raise RuntimeError("Seed route count differs from vehicle count")
        covered = [customer for route in routes for customer in route]
        if len(covered) != len(cotwin.customer_ids) or set(covered) != set(
            cotwin.customer_ids
        ):
            raise RuntimeError("Seed does not cover every customer exactly once")
        for vehicle_index, route in enumerate(routes):
            if route:
                cotwin.add_column(groups_by_vehicle[vehicle_index], route)

    @staticmethod
    def _score_routes(
        cotwin: CotVRP,
        routes: tuple[tuple[int, ...], ...],
        groups_by_vehicle: dict[int, int],
    ) -> tuple[int, int, int]:
        scores = [
            cotwin.make_column(groups_by_vehicle[index], route).score
            for index, route in enumerate(routes)
            if route
        ]
        return tuple(sum(score[i] for score in scores) for i in range(3))

    @staticmethod
    def _lp_master(
        cotwin: CotVRP, phase: str, prior: dict[str, float]
    ) -> tuple[
        pywraplp.Solver,
        dict[int, pywraplp.Constraint],
        dict[int, pywraplp.Constraint],
        dict[str, pywraplp.Constraint],
        list[pywraplp.Variable],
    ]:
        solver = pywraplp.Solver.CreateSolver("GLOP")
        if solver is None:
            raise RuntimeError("OR-Tools GLOP backend is unavailable")
        infinity = solver.infinity()
        cover = {
            customer: solver.Constraint(1, 1, f"cover_{customer}")
            for customer in cotwin.customer_ids
        }
        fleet = {
            group_index: solver.Constraint(
                -infinity, len(group.vehicle_indices), f"fleet_{group_index}"
            )
            for group_index, group in enumerate(cotwin.groups)
        }
        bounds = {
            name: solver.Constraint(-infinity, upper, f"prior_{name}")
            for name, upper in prior.items()
        }
        objective = solver.Objective()
        objective.SetMinimization()
        for index, column in enumerate(cotwin.columns.values()):
            # The covering rows already bound every nonempty route by one.
            # An explicit upper bound would add a bound dual absent from pricing.
            variable = solver.NumVar(0, infinity, f"route_{index}")
            for customer in column.customers:
                cover[customer].SetCoefficient(variable, 1)
            fleet[column.group].SetCoefficient(variable, 1)
            for name, constraint in bounds.items():
                constraint.SetCoefficient(
                    variable,
                    getattr(column, f"{name}_penalty")
                    if name != "distance"
                    else column.distance,
                )
            cost = (
                0
                if phase == "artificial"
                else (
                    column.distance
                    if phase == "distance"
                    else getattr(column, f"{phase}_penalty")
                )
            )
            objective.SetCoefficient(variable, cost)
        artificial = []
        if phase == "artificial":
            for customer in cotwin.customer_ids:
                variable = solver.NumVar(0, infinity, f"artificial_{customer}")
                cover[customer].SetCoefficient(variable, 1)
                objective.SetCoefficient(variable, 1)
                artificial.append(variable)
        return solver, cover, fleet, bounds, artificial

    def _generate(
        self,
        cotwin: CotVRP,
        phase: str,
        prior: dict[str, float],
        deadline: float,
    ) -> tuple[bool, float | None, str]:
        pricing = PricingSolver()
        rounds = 0
        while monotonic() < deadline:
            if self.pricing_mode == "fast" and rounds >= 4:
                return False, None, "HEURISTIC_ROUND_LIMIT"
            rounds += 1
            master, cover, fleet, bounds, _ = self._lp_master(cotwin, phase, prior)
            if master.Solve() != pywraplp.Solver.OPTIMAL:
                return False, None, "LP_NOT_OPTIMAL"
            value = master.Objective().Value()
            if phase == "artificial" and value <= EPSILON:
                return True, 0.0, "PHASE_ONE_COMPLETE"
            components = {
                "artificial": [0.0, 0.0, 0.0],
                "hard": [1.0, 0.0, 0.0],
                "medium": [0.0, 1.0, 0.0],
                "distance": [0.0, 0.0, 1.0],
            }[phase]
            components = components.copy()
            for name, constraint in bounds.items():
                index = ("hard", "medium", "distance").index(name)
                components[index] -= constraint.dual_value()
            if any(component < -EPSILON for component in components):
                return False, None, "NUMERICAL_DUAL_ERROR"
            components = tuple(max(0.0, component) for component in components)
            customer_duals = {c: row.dual_value() for c, row in cover.items()}
            added = 0
            all_optimal = self.pricing_mode == "exact"
            for group_index, row in fleet.items():
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False, None, "TIME_LIMIT"
                heuristic = FastPricingSolver.price(
                    cotwin,
                    group_index,
                    customer_duals,
                    row.dual_value(),
                    components,
                    min(0.5, remaining),
                )
                for result in heuristic:
                    if result.column is not None and result.reduced_cost < -EPSILON:
                        if cotwin.add_column(group_index, result.column.customers):
                            added += 1
                if self.pricing_mode == "exact" and not heuristic:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        return False, None, "TIME_LIMIT"
                    result = pricing.price(
                        cotwin,
                        group_index,
                        customer_duals,
                        row.dual_value(),
                        components,
                        min(30.0, remaining),
                    )
                    all_optimal &= result.optimal
                    if result.column is not None and result.reduced_cost < -EPSILON:
                        if cotwin.add_column(group_index, result.column.customers):
                            added += 1
                        else:
                            return False, None, "NUMERICAL_STALL"
                elif heuristic:
                    all_optimal = False
                if len(cotwin.columns) >= 10_000:
                    return False, None, "COLUMN_LIMIT"
            if added:
                print(
                    f"[{phase}] LP={value:.6g}, added={added}, columns={len(cotwin.columns)}",
                    flush=True,
                )
                continue
            if all_optimal:
                return True, value, "OPTIMAL"
            return (
                False,
                None,
                (
                    "HEURISTIC_STALLED"
                    if self.pricing_mode == "fast"
                    else "PRICING_INCOMPLETE"
                ),
            )
        return False, None, "TIME_LIMIT"

    @staticmethod
    def _solve_integer_master(
        cotwin: CotVRP,
        deadline: float,
        seed_routes: tuple[tuple[int, ...], ...] | None,
        *,
        on_solution: Callable[[tuple[int, int, int]], None] | None = None,
    ) -> tuple[tuple[tuple[int, ...], ...] | None, str]:
        if not cotwin.columns or deadline - monotonic() <= 0:
            return None, "NOT_RUN"
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if solver is None:
            raise RuntimeError("OR-Tools SCIP master backend is unavailable")
        solver.SetNumThreads(1)
        infinity = solver.infinity()
        cover = {
            customer: solver.Constraint(1, 1, f"cover_{customer}")
            for customer in cotwin.customer_ids
        }
        fleet = {
            group_index: solver.Constraint(
                -infinity, len(group.vehicle_indices), f"fleet_{group_index}"
            )
            for group_index, group in enumerate(cotwin.groups)
        }
        columns = list(cotwin.columns.values())
        variables = []
        for index, column in enumerate(columns):
            variable = solver.BoolVar(f"route_{index}")
            variables.append(variable)
            for customer in column.customers:
                cover[customer].SetCoefficient(variable, 1)
            fleet[column.group].SetCoefficient(variable, 1)
        objective = solver.Objective()
        objective.SetMinimization()
        phases = (
            ("distance",) if cotwin.mode == "strict" else ("hard", "medium", "distance")
        )
        best = None
        final_status = "NOT_RUN"
        for index, phase in enumerate(phases):
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            solver.SetTimeLimit(max(1, int(1000 * remaining / (len(phases) - index))))
            for variable, column in zip(variables, columns):
                cost = (
                    column.distance
                    if phase == "distance"
                    else getattr(column, f"{phase}_penalty")
                )
                objective.SetCoefficient(variable, cost)
            status = solver.Solve()
            final_status = {
                pywraplp.Solver.OPTIMAL: "OPTIMAL",
                pywraplp.Solver.FEASIBLE: "FEASIBLE",
                pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
            }.get(status, "UNKNOWN")
            if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
                break
            selected = [
                column
                for column, variable in zip(columns, variables)
                if variable.solution_value() > 0.5
            ]
            routes: list[tuple[int, ...]] = [() for _ in cotwin.domain.vehicles]
            for group_index, group in enumerate(cotwin.groups):
                group_routes = [c.customers for c in selected if c.group == group_index]
                for vehicle_index, route in zip(group.vehicle_indices, group_routes):
                    routes[vehicle_index] = route
            candidate = tuple(routes)
            covered = [customer for route in candidate for customer in route]
            if len(covered) != len(cotwin.customer_ids) or set(covered) != set(
                cotwin.customer_ids
            ):
                raise RuntimeError("Integer master returned incomplete routes")
            if on_solution is not None:
                on_solution(
                    tuple(sum(column.score[j] for column in selected) for j in range(3))
                )
            if seed_routes is None or candidate != seed_routes:
                best = candidate
            if status != pywraplp.Solver.OPTIMAL:
                break
            if index < len(phases) - 1:
                value = round(
                    sum(
                        c.distance
                        if phase == "distance"
                        else getattr(c, f"{phase}_penalty")
                        for c in selected
                    )
                )
                upper = solver.Constraint(-infinity, value + EPSILON, f"fix_{phase}")
                for variable, column in zip(variables, columns):
                    upper.SetCoefficient(
                        variable,
                        column.distance
                        if phase == "distance"
                        else getattr(column, f"{phase}_penalty"),
                    )
        return best, final_status

    @staticmethod
    def _result(
        cotwin: CotVRP,
        routes: tuple[tuple[int, ...], ...] | None,
        started: float,
        status: str,
        reason: str,
        lp_converged: bool = False,
        master_status: str = "NOT_RUN",
        pricing_status: str = "NOT_RUN",
        *,
        pricing_mode: str = "exact",
        generator_score: tuple[int, int, int] | None = None,
        pool_master_score: tuple[int, int, int] | None = None,
        generator_seconds: float = 0.0,
        pricing_seconds: float = 0.0,
        master_seconds: float = 0.0,
    ) -> VRPSolution:
        if routes is None:
            score = (None, None, None)
        else:
            groups_by_vehicle = {
                vehicle: group_index
                for group_index, group in enumerate(cotwin.groups)
                for vehicle in group.vehicle_indices
            }
            score = VRPSolver._score_routes(cotwin, routes, groups_by_vehicle)
        return VRPSolution(
            status,
            routes,
            *score,
            monotonic() - started,
            reason,
            lp_converged,
            master_status,
            pricing_status,
            len(cotwin.columns),
            pricing_mode,
            generator_score,
            pool_master_score,
            generator_seconds,
            pricing_seconds,
            master_seconds,
        )
