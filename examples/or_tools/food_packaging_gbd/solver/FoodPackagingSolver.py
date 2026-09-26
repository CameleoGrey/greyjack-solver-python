"""Two-stage Generalized Benders search for food packaging."""

from datetime import timedelta
from math import isfinite
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin.CotFoodPackaging import CotFoodPackaging
from .FoodPackagingSolution import FoodPackagingSolution
from .ScoreNoImprovement import ScoreNoImprovement
from .TimingSubproblem import convex_cut, earliest_schedule, solve_integer_timing


class FoodPackagingSolver:
    def __init__(
        self,
        workers: int = 10,
        no_improvement_seconds: float = 180,
        time_limit: float | None = None,
    ):
        if type(workers) is not int or workers < 1:
            raise ValueError("workers must be a positive integer")
        for name, value in (
            ("no_improvement_seconds", no_improvement_seconds),
            ("time_limit", time_limit),
        ):
            if value is None and name == "time_limit":
                continue
            if type(value) not in (float, int) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        self.workers = workers
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit

    @staticmethod
    def _mapped(cotwin, model):
        arcs = {
            key: model.get_bool_var_from_proto_index(var.index)
            for key, var in cotwin.arcs.items()
        }
        before = {
            key: model.get_bool_var_from_proto_index(var.index)
            for key, var in cotwin.operator_before.items()
        }
        hard = model.get_int_var_from_proto_index(cotwin.hard_floor.index)
        timing = model.get_int_var_from_proto_index(cotwin.timing_floor.index)
        return arcs, before, hard, timing

    @staticmethod
    def _cleaning(cotwin, arcs):
        jobs = {job.id: job for job in cotwin.domain.jobs}
        return sum(
            jobs[b].priority * cotwin.facts.cleaning[b, a] * var
            for (lid, a, b), var in arcs.items()
            if a is not None and b is not None
        )

    @staticmethod
    def _pattern(cotwin, solver, arcs, before):
        selected = []
        next_job = {}
        for key, var in arcs.items():
            if solver.value(var):
                selected.append(var)
                lid, a, b = key
                next_job[lid, a] = b
        routes = {}
        for lid in cotwin.line_ids:
            route = []
            current = next_job.get((lid, None))
            while current is not None:
                route.append(current)
                if len(route) > len(cotwin.job_ids):
                    raise RuntimeError("GBD master produced a cyclic route")
                current = next_job[lid, current]
            routes[lid] = tuple(route)
        if sorted(j for route in routes.values() for j in route) != sorted(
            cotwin.job_ids
        ):
            raise RuntimeError("GBD master omitted or duplicated a job")
        order = []
        for key, var in before.items():
            if solver.value(var):
                selected.append(var)
                order.append(key)
        return routes, order, selected

    @staticmethod
    def _no_good(model, selected):
        model.add_bool_or([var.Not() for var in selected])

    @staticmethod
    def _pattern_cost(model, theta, selected, cost):
        """Only the exact selected pattern activates this integer cost."""
        same = model.new_bool_var(
            f"evaluated_{theta.index}_{len(model.proto.constraints)}"
        )
        model.add_bool_or([var.Not() for var in selected] + [same])
        for var in selected:
            model.add_implication(same, var)
        model.add(theta >= cost).only_enforce_if(same)

    @staticmethod
    def _seed(cotwin, logger):
        if not cotwin.use_greedy_hints:
            return
        f = cotwin.facts
        routes = {lid: [] for lid in cotwin.line_ids}
        line_end = dict(f.line_start)
        operator_end = {
            line.operator: min(
                f.line_start[item.id]
                for item in cotwin.domain.lines
                if item.operator == line.operator
            )
            for line in cotwin.domain.lines
        }
        starts = {}
        for job in sorted(
            cotwin.domain.jobs, key=lambda j: (j.max_end_time, j.ideal_end_time, j.id)
        ):
            choices = []
            for line in cotwin.domain.lines:
                route = routes[line.id]
                cleanup = f.cleaning[job.id, route[-1]] if route else 0
                start = line_end[line.id] + cleanup
                if cotwin.mode == "strict":
                    start = max(start, f.min_start[job.id], operator_end[line.operator])
                end = start + f.duration[job.id]
                choices.append(
                    (
                        max(0, end - f.max_end[job.id]),
                        end,
                        line.id,
                        start,
                        line.operator,
                    )
                )
            if not choices:
                return
            _, end, lid, start, operator = min(choices)
            if cotwin.mode == "strict" and end > f.max_end[job.id]:
                return
            routes[lid].append(job.id)
            starts[job.id] = start
            line_end[lid] = end
            if cotwin.mode == "strict":
                operator_end[operator] = end
        logger.record(routes, starts)
        return routes, starts

    @staticmethod
    def _seed_literals(cotwin, routes, starts):
        selected = set()
        for lid, route in routes.items():
            if route:
                selected.add(cotwin.arcs[lid, None, route[0]].index)
                selected.add(cotwin.arcs[lid, route[-1], None].index)
                selected.update(
                    cotwin.arcs[lid, a, b].index for a, b in zip(route, route[1:])
                )
        if cotwin.mode == "strict":
            operator = {
                j: line.operator
                for line in cotwin.domain.lines
                for j in routes[line.id]
            }
            for (a, b), variable in cotwin.operator_before.items():
                if operator[a] == operator[b] and starts[a] < starts[b]:
                    selected.add(variable.index)
        return selected

    @staticmethod
    def _add_gbd_cut(cotwin, master, theta, selected, phase, logger, keys, counts):
        cut = convex_cut(
            cotwin, set(selected), phase, min(2.0, logger.remaining() / 10)
        )
        if cut is None:
            return
        intercept, coefficients = cut
        key = (phase, intercept, tuple(sorted(coefficients.items())))
        if key in keys:
            return
        master.add(
            theta
            >= intercept
            + sum(
                value * master.get_bool_var_from_proto_index(index)
                for index, value in coefficients.items()
            )
        )
        keys.add(key)
        counts["gbd_cuts"] += 1

    def _master_solve(self, model, logger):
        remaining = logger.remaining()
        if remaining <= 0:
            return None, cp_model.UNKNOWN
        error = model.validate()
        if error:
            raise ValueError(f"Invalid GBD master: {error}")
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = remaining
        logger.activate(solver)
        try:
            status = solver.solve(model)
        finally:
            logger.deactivate(solver)
        return solver, status

    def solve(self, cotwin: CotFoodPackaging) -> FoodPackagingSolution:
        started = monotonic()
        logger = ScoreNoImprovement(
            cotwin, self.no_improvement_seconds, self.time_limit
        )
        master = cotwin.master.clone()
        arcs, before, hard, timing = self._mapped(cotwin, master)
        clean = self._cleaning(cotwin, arcs)
        counts = dict(
            iterations=0,
            gbd_cuts=0,
            pattern_cuts=0,
            feasibility_cuts=0,
            timing_solves=0,
        )
        hard_lower = None
        cost_lower = None
        reason = "search_stopped"
        proven = False
        cut_keys = set()
        seen = {"hard": set(), "cost": set()}
        try:
            seed = self._seed(cotwin, logger)
            if seed is not None and logger.best_score is not None:
                seed_phase = (
                    "cost"
                    if cotwin.mode == "strict" or logger.best_score[0] == 0
                    else "hard"
                )
                self._add_gbd_cut(
                    cotwin,
                    master,
                    hard if seed_phase == "hard" else timing,
                    self._seed_literals(cotwin, *seed),
                    seed_phase,
                    logger,
                    cut_keys,
                    counts,
                )
            phases = ["cost"] if cotwin.mode == "strict" else ["hard", "cost"]
            hard_optimum = None
            for phase in phases:
                if (
                    phase == "hard"
                    and logger.best_score is not None
                    and logger.best_score[0] == 0
                ):
                    hard_optimum = 0
                    hard_lower = 0
                    continue
                if phase == "cost" and cotwin.mode == "penalized":
                    master.add(hard <= hard_optimum)
                master.minimize(hard if phase == "hard" else timing + clean)
                phase_proven = False
                while logger.remaining() > 0:
                    solver, status = self._master_solve(master, logger)
                    if status == cp_model.MODEL_INVALID:
                        raise ValueError(f"Invalid GBD master: {master.validate()}")
                    if status == cp_model.INFEASIBLE:
                        if logger.best_score is None:
                            reason = "infeasible"
                            proven = cotwin.mode == "strict"
                        else:
                            reason = "master_infeasible"
                        break
                    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                        reason = "master_unresolved"
                        break
                    routes, order, selected = self._pattern(
                        cotwin, solver, arcs, before
                    )
                    selected_ids = tuple(sorted(var.index for var in selected))
                    objective = (
                        solver.value(hard)
                        if phase == "hard"
                        else solver.value(timing)
                        + sum(
                            next(j.priority for j in cotwin.domain.jobs if j.id == b)
                            * cotwin.facts.cleaning[b, a]
                            for (lid, a, b), var in arcs.items()
                            if a is not None and b is not None and solver.value(var)
                        )
                    )
                    if status == cp_model.OPTIMAL:
                        if phase == "hard":
                            hard_lower = objective
                            if (
                                logger.best_score is not None
                                and objective >= logger.best_score[0]
                            ):
                                hard_optimum = logger.best_score[0]
                                phase_proven = True
                                break
                        else:
                            cost_lower = objective
                            if logger.best_score is not None and objective >= (
                                cotwin.facts.medium_weight * logger.best_score[1]
                                + logger.best_score[2]
                            ):
                                phase_proven = True
                                proven = True
                                reason = "optimal"
                                break
                    if selected_ids in seen[phase]:
                        reason = "master_stalled"
                        break
                    seen[phase].add(selected_ids)
                    counts["iterations"] += 1
                    exact = earliest_schedule(cotwin, routes, order)
                    if not exact.feasible:
                        self._no_good(master, selected)
                        counts["feasibility_cuts"] += 1
                        continue
                    if phase == "hard":
                        logger.record(routes, exact.starts)
                        self._add_gbd_cut(
                            cotwin,
                            master,
                            hard,
                            selected_ids,
                            "hard",
                            logger,
                            cut_keys,
                            counts,
                        )
                        self._pattern_cost(master, hard, selected, exact.hard)
                        counts["pattern_cuts"] += 1
                        if exact.hard == 0:
                            hard_optimum = 0
                            hard_lower = 0
                            phase_proven = True
                            break
                        continue
                    if cotwin.mode == "penalized" and exact.hard > hard_optimum:
                        self._add_gbd_cut(
                            cotwin,
                            master,
                            hard,
                            selected_ids,
                            "hard",
                            logger,
                            cut_keys,
                            counts,
                        )
                        self._no_good(master, selected)
                        counts["feasibility_cuts"] += 1
                        continue
                    self._add_gbd_cut(
                        cotwin,
                        master,
                        timing,
                        selected_ids,
                        "cost",
                        logger,
                        cut_keys,
                        counts,
                    )
                    if cotwin.mode == "strict":
                        logger.record(routes, exact.starts)
                        cost = cotwin.facts.medium_weight * exact.medium + exact.ideal
                    else:
                        logger.record(routes, exact.starts)
                        status_t, cost = solve_integer_timing(
                            cotwin,
                            routes,
                            hard_optimum,
                            logger.remaining(),
                            logger.record,
                            logger.activate,
                            logger.deactivate,
                            self.workers,
                        )
                        counts["timing_solves"] += 1
                        if status_t != cp_model.OPTIMAL:
                            reason = "subproblem_unresolved"
                            break
                    self._pattern_cost(master, timing, selected, cost)
                    counts["pattern_cuts"] += 1
                if phase == "hard":
                    if hard_optimum is None:
                        break
                    if not phase_proven:
                        break
            if logger.remaining() <= 0 and not proven:
                reason = logger.reason()
        finally:
            logger.close()
        elapsed = monotonic() - started
        if proven:
            status_name = "INFEASIBLE" if reason == "infeasible" else "OPTIMAL"
        elif logger.best_score is not None:
            status_name = "FEASIBLE"
        else:
            status_name = "UNKNOWN"
        starts = (
            None
            if logger.best_starts is None
            else {
                j: cotwin.origin + timedelta(minutes=value)
                for j, value in logger.best_starts.items()
            }
        )
        score = logger.best_score or (None, None, None)
        return FoodPackagingSolution(
            status_name,
            logger.best_routes,
            starts,
            *score,
            elapsed,
            reason,
            cotwin.mode,
            **counts,
            hard_lower_bound=hard_lower,
            cost_lower_bound=cost_lower,
        )
