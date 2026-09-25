"""Build the assignment master and exact crew timing models."""

from copy import deepcopy
from dataclasses import dataclass, field
from itertools import combinations

from ortools.sat.python import cp_model

from ..cotwin import CotCrewSubproblem, CotMaintenanceSchedule
from ..domain import Job, MaintenanceSchedule


def _raw_overlap_bounds(
    start_days: tuple[int, ...],
    end_days: dict[int, tuple[int, ...]],
    first_id: int,
    second_id: int,
) -> tuple[int, int]:
    first, second = end_days[first_id], end_days[second_id]
    return (
        min(min(first), min(second)) - max(start_days),
        min(max(first), max(second)) - min(start_days),
    )


def _date_penalties(job: Job, start_day: int, end_day: int) -> tuple[int, int]:
    hard = 0
    soft = 0
    if job.min_start_date is not None:
        hard += max(0, job.min_start_date.toordinal() - start_day)
    if job.max_end_date is not None:
        hard += max(0, end_day - job.max_end_date.toordinal())
    if job.ideal_end_date is not None:
        ideal = job.ideal_end_date.toordinal()
        soft += int(end_day < ideal) + 1_000_000 * int(end_day > ideal)
    return hard, soft


@dataclass
class _TimingState:
    starts: dict[int, cp_model.IntVar] = field(default_factory=dict)
    start_dates: dict[int, cp_model.IntVar] = field(default_factory=dict)
    end_dates: dict[int, cp_model.IntVar] = field(default_factory=dict)
    hard_terms: list = field(default_factory=list)
    soft_terms: list = field(default_factory=list)
    intervals: list[cp_model.IntervalVar] = field(default_factory=list)


class CotwinBuilder:
    """Encode crew choices in the master and timing in separate subproblems."""

    def __init__(self, *, mode: str = "strict") -> None:
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode

    def build_cotwin(self, domain: MaintenanceSchedule) -> CotMaintenanceSchedule:
        domain.validate()
        snapshot = deepcopy(domain)
        crew_ids = tuple(crew.crew_id for crew in snapshot.crews)
        start_days = tuple(
            day.toordinal() for day in snapshot.work_calendar.work_day_list
        )
        end_days = {
            job.job_id: tuple(
                snapshot.work_calendar.end_date(index, job.duration_in_days).toordinal()
                for index in range(len(start_days))
            )
            for job in snapshot.jobs
        }
        allowed_starts = self._allowed_starts(snapshot, start_days, end_days)
        hard_upper, soft_upper = self._score_bounds(snapshot, start_days, end_days)
        hard_weight = soft_upper + 1
        cost_upper = (
            soft_upper
            if self.mode == "strict"
            else hard_weight * hard_upper + soft_upper
        )
        safe_bound = cp_model.INT_MAX // 2
        if (
            max(hard_upper, soft_upper, hard_weight, cost_upper * max(1, len(crew_ids)))
            > safe_bound
        ):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")

        individual_costs = {}
        for job in snapshot.jobs:
            options = []
            for index in allowed_starts[job.job_id]:
                hard, soft = _date_penalties(
                    job, start_days[index], end_days[job.job_id][index]
                )
                options.append(
                    hard_weight * hard + soft if self.mode == "penalized" else soft
                )
            individual_costs[job.job_id] = min(options, default=0)

        master = cp_model.CpModel()
        assignments = self._add_master_assignments(master, snapshot, crew_ids)
        if self.mode == "strict" and any(
            not starts for starts in allowed_starts.values()
        ):
            master.add_bool_or([])
        crew_costs = self._add_master_costs(
            master, snapshot, crew_ids, assignments, individual_costs, cost_upper
        )
        master.minimize(sum(crew_costs.values()))
        validation_error = master.validate()
        if validation_error:
            raise ValueError(f"Invalid Benders master: {validation_error}")
        return CotMaintenanceSchedule(
            snapshot,
            master,
            assignments,
            crew_costs,
            crew_ids,
            start_days,
            end_days,
            allowed_starts,
            individual_costs,
            hard_weight,
            hard_upper,
            soft_upper,
            cost_upper,
            self.mode,
        )

    def _allowed_starts(
        self,
        domain: MaintenanceSchedule,
        start_days: tuple[int, ...],
        end_days: dict[int, tuple[int, ...]],
    ) -> dict[int, tuple[int, ...]]:
        result = {}
        for job in domain.jobs:
            result[job.job_id] = tuple(
                index
                for index, start in enumerate(start_days)
                if self.mode == "penalized"
                or (
                    (
                        job.min_start_date is None
                        or start >= job.min_start_date.toordinal()
                    )
                    and (
                        job.max_end_date is None
                        or end_days[job.job_id][index] <= job.max_end_date.toordinal()
                    )
                )
            )
        return result

    @staticmethod
    def _score_bounds(
        domain: MaintenanceSchedule,
        start_days: tuple[int, ...],
        end_days: dict[int, tuple[int, ...]],
    ) -> tuple[int, int]:
        hard_upper = 0
        soft_upper = 0
        for job in domain.jobs:
            rows = [
                _date_penalties(job, start_days[index], end_days[job.job_id][index])
                for index in range(len(start_days))
            ]
            hard_upper += max(hard for hard, _ in rows)
            soft_upper += max(soft for _, soft in rows)
        for first, second in combinations(domain.jobs, 2):
            lower, upper = _raw_overlap_bounds(
                start_days, end_days, first.job_id, second.job_id
            )
            hard_upper += 2 * max(0, upper)
            common_tags = len(set(first.tags) & set(second.tags))
            soft_upper += 2_000 * common_tags * max(abs(lower), abs(upper))
        return hard_upper, soft_upper

    @staticmethod
    def _add_master_assignments(
        model: cp_model.CpModel,
        domain: MaintenanceSchedule,
        crew_ids: tuple[int, ...],
    ) -> dict[int, dict[int, cp_model.IntVar]]:
        assignments = {}
        for job in domain.jobs:
            row = {
                crew_id: model.new_bool_var(f"assign_{job.job_id}_{crew_id}")
                for crew_id in crew_ids
            }
            model.add_exactly_one(row.values())
            assignments[job.job_id] = row
        # Current crews differ only by their labels. Sorting crew loads removes
        # equivalent label permutations without excluding a business schedule.
        for left, right in zip(crew_ids, crew_ids[1:]):
            model.add(
                sum(row[left] for row in assignments.values())
                >= sum(row[right] for row in assignments.values())
            )
        return assignments

    @staticmethod
    def _add_master_costs(
        model: cp_model.CpModel,
        domain: MaintenanceSchedule,
        crew_ids: tuple[int, ...],
        assignments: dict[int, dict[int, cp_model.IntVar]],
        individual_costs: dict[int, int],
        cost_upper: int,
    ) -> dict[int, cp_model.IntVar]:
        costs = {}
        for crew_id in crew_ids:
            theta = model.new_int_var(0, cost_upper, f"crew_cost_{crew_id}")
            model.add(
                theta
                >= sum(
                    individual_costs[job.job_id] * assignments[job.job_id][crew_id]
                    for job in domain.jobs
                )
            )
            costs[crew_id] = theta
        return costs

    def build_crew_subproblem(
        self, cotwin: CotMaintenanceSchedule, job_ids: frozenset[int]
    ) -> CotCrewSubproblem:
        """Find the exact minimum timing cost for one crew's assigned jobs."""
        jobs = [job for job in cotwin.domain.jobs if job.job_id in job_ids]
        if len(jobs) != len(job_ids):
            raise ValueError("Subproblem contains an unknown job ID")
        model = cp_model.CpModel()
        timing = self._add_job_timing(model, cotwin, jobs)
        if cotwin.mode == "strict" and timing.intervals:
            model.add_no_overlap(timing.intervals)
        self._add_pair_penalties(model, cotwin, jobs, timing)
        hard = model.new_int_var(0, cotwin.hard_upper_bound, "hard_penalty")
        soft = model.new_int_var(0, cotwin.soft_upper_bound, "soft_penalty")
        model.add(hard == sum(timing.hard_terms))
        model.add(soft == sum(timing.soft_terms))
        if cotwin.mode == "strict":
            model.add(hard == 0)
            model.minimize(soft)
        else:
            model.minimize(cotwin.hard_weight * hard + soft)
        validation_error = model.validate()
        if validation_error:
            raise ValueError(f"Invalid crew subproblem: {validation_error}")
        return CotCrewSubproblem(model, timing.starts, hard, soft)

    @staticmethod
    def _add_job_timing(
        model: cp_model.CpModel,
        cotwin: CotMaintenanceSchedule,
        jobs: list[Job],
    ) -> _TimingState:
        state = _TimingState()
        for job in jobs:
            jid = job.job_id
            allowed = cotwin.allowed_starts[jid]
            if not allowed:
                model.add_bool_or([])
                allowed = (0,)
            index = model.new_int_var_from_domain(
                cp_model.Domain.from_values(allowed), f"start_id_{jid}"
            )
            start = model.new_int_var(
                min(cotwin.start_days), max(cotwin.start_days), f"start_date_{jid}"
            )
            ends = cotwin.end_days[jid]
            end = model.new_int_var(min(ends), max(ends), f"end_date_{jid}")
            model.add_element(index, cotwin.start_days, start)
            model.add_element(index, ends, end)
            state.starts[jid] = index
            state.start_dates[jid] = start
            state.end_dates[jid] = end
            rows = [
                _date_penalties(job, day, ends[i])
                for i, day in enumerate(cotwin.start_days)
            ]
            for label, column, terms in (
                ("hard_date", 0, state.hard_terms),
                ("soft_date", 1, state.soft_terms),
            ):
                values = [row[column] for row in rows]
                penalty = model.new_int_var(0, max(values), f"{label}_{jid}")
                model.add_element(index, values, penalty)
                terms.append(penalty)
            if cotwin.mode == "strict":
                span = model.new_int_var(
                    1, max(ends) - min(cotwin.start_days), f"span_{jid}"
                )
                model.add(span == end - start)
                state.intervals.append(
                    model.new_interval_var(start, span, end, f"job_{jid}")
                )
        return state

    @staticmethod
    def _add_pair_penalties(
        model: cp_model.CpModel,
        cotwin: CotMaintenanceSchedule,
        jobs: list[Job],
        timing: _TimingState,
    ) -> None:
        for first, second in combinations(jobs, 2):
            a, b = first.job_id, second.job_id
            common_tags = len(set(first.tags) & set(second.tags))
            if cotwin.mode == "strict" and not common_tags:
                continue
            lower, upper = _raw_overlap_bounds(cotwin.start_days, cotwin.end_days, a, b)
            min_end = model.new_int_var(
                min(min(cotwin.end_days[a]), min(cotwin.end_days[b])),
                min(max(cotwin.end_days[a]), max(cotwin.end_days[b])),
                f"min_end_{a}_{b}",
            )
            max_start = model.new_int_var(
                min(cotwin.start_days), max(cotwin.start_days), f"max_start_{a}_{b}"
            )
            raw = model.new_int_var(lower, upper, f"raw_overlap_{a}_{b}")
            model.add_min_equality(min_end, [timing.end_dates[a], timing.end_dates[b]])
            model.add_max_equality(
                max_start, [timing.start_dates[a], timing.start_dates[b]]
            )
            model.add(raw == min_end - max_start)
            if cotwin.mode == "penalized":
                positive = model.new_int_var(0, max(0, upper), f"positive_{a}_{b}")
                model.add_max_equality(positive, [0, raw])
                timing.hard_terms.append(2 * positive)
            if common_tags:
                absolute = model.new_int_var(
                    0, max(abs(lower), abs(upper)), f"absolute_{a}_{b}"
                )
                model.add_abs_equality(absolute, raw)
                timing.soft_terms.append(2_000 * common_tags * absolute)
