"""Exact logic-based Benders search for maintenance scheduling."""

from copy import deepcopy
from dataclasses import dataclass
from math import floor, isfinite
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin import CotMaintenanceSchedule
from ..persistence.CotwinBuilder import CotwinBuilder, _date_penalties
from .MaintenanceSchedulingSolution import MaintenanceSchedulingSolution
from .ScoreNoImprovement import ScoreNoImprovement


@dataclass(frozen=True)
class _CrewResult:
    status: int
    starts: dict[int, int] | None
    hard: int | None
    soft: int | None
    lower_bound: int | None


class MaintenanceSchedulingSolver:
    def __init__(
        self,
        workers: int = 10,
        no_improvement_seconds: float = 30,
        time_limit: float | None = None,
    ) -> None:
        if type(workers) is not int or workers < 1:
            raise ValueError("workers must be a positive integer")
        for name, value in (
            ("no_improvement_seconds", no_improvement_seconds),
            ("time_limit", time_limit),
        ):
            if name == "time_limit" and value is None:
                continue
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        self.workers = workers
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit

    def solve(self, cotwin: CotMaintenanceSchedule) -> MaintenanceSchedulingSolution:
        validation_error = cotwin.master.validate()
        if validation_error:
            raise ValueError(f"Invalid Benders master: {validation_error}")
        started = monotonic()
        global_deadline = (
            float("inf") if self.time_limit is None else started + self.time_limit
        )
        logger = ScoreNoImprovement(started, self.no_improvement_seconds)
        master = cotwin.master.clone()
        assignments = {
            jid: {
                cid: master.get_bool_var_from_proto_index(variable.index)
                for cid, variable in row.items()
            }
            for jid, row in cotwin.assignments.items()
        }
        crew_costs = {
            cid: master.get_int_var_from_proto_index(variable.index)
            for cid, variable in cotwin.crew_costs.items()
        }
        total_cost = sum(crew_costs.values())
        builder = CotwinBuilder(mode=cotwin.mode)
        cache: dict[frozenset[int], _CrewResult] = {}
        cut_bounds: dict[frozenset[int], int] = {}
        infeasible_subsets: set[frozenset[int]] = set()
        skipped_assignments: set[tuple[int, ...]] = set()
        iterations = 0
        cuts = 0
        capacity_cut_count = 0
        subproblem_cut_count = 0
        unresolved_reason = "search_stopped"

        self._seed(cotwin, logger, global_deadline)
        if logger.best_score is not None:
            master.add(total_cost <= self._weighted_cost(cotwin, logger.best_score) - 1)
        windows = self._capacity_windows(cotwin)
        full_window = windows[-1]
        for cid in cotwin.crew_ids:
            self._add_capacity_cut(
                master, cotwin, assignments, crew_costs, cid, full_window
            )
            cuts += 1
            capacity_cut_count += 1
        capacity_cuts = {
            (cid, full_window[0], full_window[1]) for cid in cotwin.crew_ids
        }

        while self._remaining(logger, global_deadline) > 0:
            search_model = master.clone()
            search_assignments = {
                jid: {
                    cid: search_model.get_bool_var_from_proto_index(variable.index)
                    for cid, variable in row.items()
                }
                for jid, row in assignments.items()
            }
            for selected in skipped_assignments:
                search_model.add(
                    sum(
                        search_assignments[jid][cid]
                        for jid, cid in zip(assignments, selected)
                    )
                    <= len(selected) - 1
                )
            self._set_search_objective(search_model, cotwin, search_assignments)
            master_solver = self._new_cp_solver(
                min(2.0, self._remaining(logger, global_deadline))
            )
            status = master_solver.solve(search_model)
            if status == cp_model.INFEASIBLE:
                if skipped_assignments:
                    unresolved_reason = "subproblem_unresolved"
                    break
                return self._finish(
                    cotwin,
                    logger,
                    started,
                    "OPTIMAL" if logger.best_score is not None else "INFEASIBLE",
                    "optimal" if logger.best_score is not None else "infeasible",
                    iterations,
                    cuts,
                    capacity_cut_count,
                    subproblem_cut_count,
                )
            if status == cp_model.MODEL_INVALID:
                raise ValueError(f"Invalid Benders master: {search_model.validate()}")
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                if self._remaining(logger, global_deadline) <= 0:
                    unresolved_reason = "master_unresolved"
                    break
                continue

            iterations += 1
            subsets = {cid: set() for cid in cotwin.crew_ids}
            for jid, row in assignments.items():
                selected = [
                    cid
                    for cid, variable in row.items()
                    if master_solver.value(search_assignments[jid][cid])
                ]
                if len(selected) != 1:
                    raise RuntimeError(f"Master did not assign job {jid} exactly once")
                subsets[selected[0]].add(jid)
            selected_assignment = tuple(
                next(cid for cid in cotwin.crew_ids if jid in subsets[cid])
                for jid in assignments
            )

            new_capacity_cuts = self._separate_capacity_cuts(
                master,
                search_model,
                master_solver,
                cotwin,
                assignments,
                crew_costs,
                subsets,
                windows,
                capacity_cuts,
            )
            if new_capacity_cuts:
                cuts += new_capacity_cuts
                capacity_cut_count += new_capacity_cuts
                continue

            candidate: dict[int, tuple[int, int]] = {}
            expected_hard = 0
            expected_soft = 0
            incomplete = False
            infeasible = False
            if cotwin.mode == "penalized":
                candidate = self._independent_candidate(cotwin, subsets)
                logger.record(self._replay(cotwin, candidate), candidate)
                if logger.best_score is not None:
                    master.add(
                        total_cost <= self._weighted_cost(cotwin, logger.best_score) - 1
                    )
            for cid, subset in subsets.items():
                key = frozenset(subset)
                result = cache.get(key)
                if result is None:
                    pending = sum(bool(value) for value in subsets.values())
                    result = self._solve_crew(
                        builder,
                        cotwin,
                        key,
                        min(
                            2.0,
                            max(
                                0.001,
                                self._remaining(logger, global_deadline)
                                / (pending + 1),
                            ),
                        ),
                        {jid: candidate[jid][1] for jid in key if jid in candidate},
                    )
                    if result is None:
                        incomplete = True
                        break
                    if result.status in (cp_model.OPTIMAL, cp_model.INFEASIBLE):
                        cache[key] = result
                if result.status == cp_model.MODEL_INVALID:
                    raise ValueError("Invalid crew timing model")
                if result.status == cp_model.INFEASIBLE:
                    if key not in infeasible_subsets:
                        for other_cid in cotwin.crew_ids:
                            master.add(
                                sum(assignments[jid][other_cid] for jid in key)
                                <= len(key) - 1
                            )
                            cuts += 1
                            subproblem_cut_count += 1
                        infeasible_subsets.add(key)
                    infeasible = True
                    break
                if (
                    result.starts is not None
                    and result.hard is not None
                    and result.soft is not None
                ):
                    expected_hard += result.hard
                    expected_soft += result.soft
                    candidate.update(
                        {jid: (cid, day) for jid, day in result.starts.items()}
                    )
                else:
                    incomplete = True
                if result.status != cp_model.OPTIMAL:
                    incomplete = True

                if key and result.lower_bound is not None:
                    baseline = sum(cotwin.individual_costs[jid] for jid in key)
                    lower = max(baseline, result.lower_bound)
                    if lower > cut_bounds.get(key, baseline):
                        extra = lower - baseline
                        for other_cid in cotwin.crew_ids:
                            base = sum(
                                cost * assignments[jid][other_cid]
                                for jid, cost in cotwin.individual_costs.items()
                            )
                            master.add(
                                crew_costs[other_cid] >= base + extra
                            ).only_enforce_if(
                                [assignments[jid][other_cid] for jid in key]
                            )
                            cuts += 1
                            subproblem_cut_count += 1
                        cut_bounds[key] = lower

            if infeasible:
                continue
            if len(candidate) == len(cotwin.domain.jobs):
                score = self._replay(cotwin, candidate)
                if not incomplete and score != (expected_hard, expected_soft):
                    raise RuntimeError(
                        "Crew subproblem scores disagree with business replay"
                    )
                if logger.record(score, candidate):
                    master.add(total_cost <= self._weighted_cost(cotwin, score) - 1)
            if incomplete:
                skipped_assignments.add(selected_assignment)
                unresolved_reason = "subproblem_unresolved"

        reason = self._stop_reason(logger, global_deadline, unresolved_reason)
        return self._finish(
            cotwin,
            logger,
            started,
            "FEASIBLE" if logger.best_score is not None else "UNKNOWN",
            reason,
            iterations,
            cuts,
            capacity_cut_count,
            subproblem_cut_count,
        )

    def _seed(
        self,
        cotwin: CotMaintenanceSchedule,
        logger: ScoreNoImprovement,
        global_deadline: float,
    ) -> None:
        if not cotwin.domain.jobs:
            logger.record((0, 0), {})
            return
        if cotwin.mode == "penalized":
            subsets = {cid: set() for cid in cotwin.crew_ids}
            for index, job in enumerate(cotwin.domain.jobs):
                subsets[cotwin.crew_ids[index % len(cotwin.crew_ids)]].add(job.job_id)
            candidate = self._independent_candidate(cotwin, subsets)
            logger.record(self._replay(cotwin, candidate), candidate)
            self._improve_candidate(cotwin, logger, candidate, global_deadline, 1.5)
            return
        if any(not starts for starts in cotwin.allowed_starts.values()):
            return
        # Greedy crew-wise insertion is a primal heuristic, not a proof.
        candidate: dict[int, tuple[int, int]] = {}
        jobs = sorted(
            cotwin.domain.jobs,
            key=lambda job: (len(cotwin.allowed_starts[job.job_id]), job.job_id),
        )
        for job in jobs:
            jid = job.job_id
            choices = []
            for cid in cotwin.crew_ids:
                for day in cotwin.allowed_starts[jid]:
                    start, end = cotwin.start_days[day], cotwin.end_days[jid][day]
                    if any(
                        other_cid == cid
                        and start < cotwin.end_days[other_jid][other_day]
                        and cotwin.start_days[other_day] < end
                        for other_jid, (other_cid, other_day) in candidate.items()
                    ):
                        continue
                    soft = _date_penalties(job, start, end)[1]
                    load = sum(other_cid == cid for other_cid, _ in candidate.values())
                    choices.append((soft, load, cid, day))
            if not choices:
                return
            _, _, cid, day = min(choices)
            candidate[jid] = (cid, day)
        logger.record(self._replay(cotwin, candidate), candidate)
        self._improve_candidate(cotwin, logger, candidate, global_deadline, 1.5)

    @staticmethod
    def _independent_candidate(
        cotwin: CotMaintenanceSchedule, subsets: dict[int, set[int]]
    ) -> dict[int, tuple[int, int]]:
        jobs = {job.job_id: job for job in cotwin.domain.jobs}
        candidate = {}
        for cid, subset in subsets.items():
            for jid in subset:
                job = jobs[jid]
                day = min(
                    cotwin.allowed_starts[jid],
                    key=lambda index: (
                        cotwin.hard_weight
                        * _date_penalties(
                            job, cotwin.start_days[index], cotwin.end_days[jid][index]
                        )[0]
                        + _date_penalties(
                            job, cotwin.start_days[index], cotwin.end_days[jid][index]
                        )[1],
                        index,
                    ),
                )
                candidate[jid] = (cid, day)
        return candidate

    @staticmethod
    def _capacity_windows(
        cotwin: CotMaintenanceSchedule,
    ) -> list[tuple[int, int, dict[int, int]]]:
        if not cotwin.domain.jobs:
            return [(0, 1, {})]
        options = {
            job.job_id: [
                (cotwin.start_days[day], cotwin.end_days[job.job_id][day])
                for day in cotwin.allowed_starts[job.job_id]
            ]
            for job in cotwin.domain.jobs
        }
        full = (
            min(cotwin.start_days),
            max(end for row in cotwin.end_days.values() for end in row),
        )
        pairs = {
            (min(start for start, _ in row), max(end for _, end in row))
            for row in options.values()
            if row
        }
        pairs.discard(full)
        ordered = sorted(pairs) + [full]
        windows = []
        for left, right in ordered:
            minimum = {
                jid: min(
                    max(0, min(end, right) - max(start, left)) for start, end in row
                )
                for jid, row in options.items()
                if row
            }
            windows.append((left, right, minimum))
        return windows

    @staticmethod
    def _add_capacity_cut(
        model: cp_model.CpModel,
        cotwin: CotMaintenanceSchedule,
        assignments: dict[int, dict[int, cp_model.IntVar]],
        crew_costs: dict[int, cp_model.IntVar],
        cid: int,
        window: tuple[int, int, dict[int, int]],
    ) -> None:
        left, right, minimum = window
        occupancy = sum(value * assignments[jid][cid] for jid, value in minimum.items())
        if cotwin.mode == "strict":
            model.add(occupancy <= right - left)
        else:
            base = sum(
                cost * assignments[jid][cid]
                for jid, cost in cotwin.individual_costs.items()
            )
            model.add(
                crew_costs[cid]
                >= base + 2 * cotwin.hard_weight * (occupancy - (right - left))
            )

    def _separate_capacity_cuts(
        self,
        master: cp_model.CpModel,
        search_model: cp_model.CpModel,
        solver: cp_model.CpSolver,
        cotwin: CotMaintenanceSchedule,
        assignments: dict[int, dict[int, cp_model.IntVar]],
        crew_costs: dict[int, cp_model.IntVar],
        subsets: dict[int, set[int]],
        windows: list[tuple[int, int, dict[int, int]]],
        known: set[tuple[int, int, int]],
    ) -> int:
        added = 0
        for cid, subset in subsets.items():
            theta = solver.value(
                search_model.get_int_var_from_proto_index(crew_costs[cid].index)
            )
            base = sum(cotwin.individual_costs[jid] for jid in subset)
            violated = []
            for window in windows:
                left, right, minimum = window
                if (cid, left, right) in known:
                    continue
                load = sum(minimum.get(jid, 0) for jid in subset)
                if cotwin.mode == "strict":
                    excess = load - (right - left)
                else:
                    excess = (
                        base + 2 * cotwin.hard_weight * (load - (right - left)) - theta
                    )
                if excess > 0:
                    violated.append((excess, window))
            for _, window in sorted(violated, key=lambda item: item[0], reverse=True)[
                :2
            ]:
                self._add_capacity_cut(
                    master, cotwin, assignments, crew_costs, cid, window
                )
                known.add((cid, window[0], window[1]))
                added += 1
        return added

    @staticmethod
    def _set_search_objective(
        model: cp_model.CpModel,
        cotwin: CotMaintenanceSchedule,
        assignments: dict[int, dict[int, cp_model.IntVar]],
    ) -> None:
        spans = {
            jid: min(
                cotwin.end_days[jid][day] - cotwin.start_days[day]
                for day in cotwin.allowed_starts[jid]
            )
            for jid in assignments
            if cotwin.allowed_starts[jid]
        }
        upper = sum(spans.values())
        max_load = model.new_int_var(0, upper, "search_max_load")
        for cid in cotwin.crew_ids:
            model.add(
                max_load
                >= sum(span * assignments[jid][cid] for jid, span in spans.items())
            )
        model.minimize(max_load)

    def _improve_candidate(
        self,
        cotwin: CotMaintenanceSchedule,
        logger: ScoreNoImprovement,
        candidate: dict[int, tuple[int, int]],
        global_deadline: float,
        seconds: float,
    ) -> None:
        deadline = min(monotonic() + seconds, logger.deadline, global_deadline)
        jobs = {job.job_id: job for job in cotwin.domain.jobs}
        tags = {jid: set(job.tags) for jid, job in jobs.items()}
        score = self._replay(cotwin, candidate)
        while monotonic() < deadline:
            best_score, best_move = score, None
            for jid, job in jobs.items():
                old_cid, old_day = candidate[jid]
                old_start = cotwin.start_days[old_day]
                old_end = cotwin.end_days[jid][old_day]
                old_date = _date_penalties(job, old_start, old_end)
                for cid in cotwin.crew_ids:
                    for day in cotwin.allowed_starts[jid]:
                        if (cid, day) == (old_cid, old_day):
                            continue
                        start, end = cotwin.start_days[day], cotwin.end_days[jid][day]
                        new_date = _date_penalties(job, start, end)
                        delta_hard = new_date[0] - old_date[0]
                        delta_soft = new_date[1] - old_date[1]
                        for other_id, (other_cid, other_day) in candidate.items():
                            if other_id == jid or other_cid not in (old_cid, cid):
                                continue
                            other_start = cotwin.start_days[other_day]
                            other_end = cotwin.end_days[other_id][other_day]
                            shared = len(tags[jid] & tags[other_id])
                            if other_cid == old_cid:
                                raw = min(old_end, other_end) - max(
                                    old_start, other_start
                                )
                                delta_hard -= 2 * max(0, raw)
                                delta_soft -= 2_000 * shared * abs(raw)
                            if other_cid == cid:
                                raw = min(end, other_end) - max(start, other_start)
                                delta_hard += 2 * max(0, raw)
                                delta_soft += 2_000 * shared * abs(raw)
                        new_score = (score[0] + delta_hard, score[1] + delta_soft)
                        if cotwin.mode == "strict" and new_score[0] != 0:
                            continue
                        if new_score < best_score:
                            best_score, best_move = new_score, (jid, cid, day)
                if monotonic() >= deadline:
                    break
            if best_move is None:
                break
            jid, cid, day = best_move
            candidate[jid] = (cid, day)
            score = self._replay(cotwin, candidate)
            if score != best_score:
                raise RuntimeError("Primal move score disagrees with business replay")
            logger.record(score, candidate)

    def _solve_crew(
        self,
        builder: CotwinBuilder,
        cotwin: CotMaintenanceSchedule,
        jobs: frozenset[int],
        budget: float,
        hints: dict[int, int],
    ) -> _CrewResult | None:
        if not jobs:
            return _CrewResult(cp_model.OPTIMAL, {}, 0, 0, 0)
        if budget <= 0:
            return None
        subproblem = builder.build_crew_subproblem(cotwin, jobs)
        for jid, day in hints.items():
            subproblem.model.add_hint(subproblem.start_variables[jid], day)
        solver = self._new_cp_solver(budget)
        status = solver.solve(subproblem.model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return _CrewResult(status, None, None, None, None)
        return _CrewResult(
            status,
            {jid: solver.value(var) for jid, var in subproblem.start_variables.items()},
            solver.value(subproblem.hard_penalty),
            solver.value(subproblem.soft_penalty),
            floor(solver.best_objective_bound),
        )

    def _new_cp_solver(self, seconds: float) -> cp_model.CpSolver:
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = max(0.001, seconds)
        return solver

    @staticmethod
    def _replay(
        cotwin: CotMaintenanceSchedule, assignments: dict[int, tuple[int, int]]
    ) -> tuple[int, int]:
        domain = deepcopy(cotwin.domain)
        if set(assignments) != {job.job_id for job in domain.jobs}:
            raise RuntimeError("Candidate does not cover every job")
        for job in domain.jobs:
            job.crew_id, job.start_date_id = assignments[job.job_id]
        metrics = domain.calculate_metrics()
        return metrics["hard_penalty"], metrics["soft_penalty"]

    @staticmethod
    def _weighted_cost(cotwin: CotMaintenanceSchedule, score: tuple[int, int]) -> int:
        return (
            score[1]
            if cotwin.mode == "strict"
            else cotwin.hard_weight * score[0] + score[1]
        )

    @staticmethod
    def _remaining(logger: ScoreNoImprovement, global_deadline: float) -> float:
        return min(logger.deadline, global_deadline) - monotonic()

    @staticmethod
    def _stop_reason(
        logger: ScoreNoImprovement, global_deadline: float, fallback: str
    ) -> str:
        now = monotonic()
        # CP-SAT may return just before its own wall-time cap.
        slack = 0.05
        if now + slack >= global_deadline and global_deadline <= logger.deadline:
            return "time_limit"
        if now + slack >= logger.deadline:
            return "no_improvement"
        return fallback

    @staticmethod
    def _finish(
        cotwin: CotMaintenanceSchedule,
        logger: ScoreNoImprovement,
        started: float,
        status: str,
        reason: str,
        iterations: int,
        cuts: int,
        capacity_cuts: int,
        subproblem_cuts: int,
    ) -> MaintenanceSchedulingSolution:
        score = logger.best_score
        return MaintenanceSchedulingSolution(
            status,
            logger.best_assignments,
            None if score is None else score[0],
            None if score is None else score[1],
            monotonic() - started,
            reason,
            cotwin.mode,
            iterations,
            cuts,
            capacity_cuts,
            subproblem_cuts,
        )
