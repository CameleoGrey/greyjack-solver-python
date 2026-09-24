from dataclasses import dataclass, field
from itertools import combinations

from ortools.sat.python import cp_model

from ..cotwin import CotMaintenanceSchedule
from ..domain import Job, MaintenanceSchedule


_PENALTY_NAMES = (
    "crew_overlap_penalty",
    "early_start_penalty",
    "late_end_penalty",
    "before_ideal_penalty",
    "after_ideal_penalty",
    "tag_penalty",
)


@dataclass
class _ModelState:
    """Variables and score terms shared by the model-building steps."""

    model: cp_model.CpModel
    crew_ids: tuple[int, ...]
    start_days: list[int]
    crew_intervals: dict[int, list[cp_model.IntervalVar]]
    terms: dict[str, list] = field(
        default_factory=lambda: {name: [] for name in _PENALTY_NAMES}
    )
    bounds: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(_PENALTY_NAMES, 0)
    )
    crew_variables: dict[int, cp_model.IntVar] = field(default_factory=dict)
    start_variables: dict[int, cp_model.IntVar] = field(default_factory=dict)
    start_dates: dict[int, cp_model.IntVar] = field(default_factory=dict)
    end_dates: dict[int, cp_model.IntVar] = field(default_factory=dict)
    end_rows: dict[int, list[int]] = field(default_factory=dict)


class CotwinBuilder:
    """Encode the original hard/soft score in integer CP-SAT constraints."""

    def __init__(self, *, mode: str = "strict") -> None:
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode

    def build_cotwin(self, domain: MaintenanceSchedule) -> CotMaintenanceSchedule:
        domain.validate()
        crew_ids = tuple(crew.crew_id for crew in domain.crews)
        state = _ModelState(
            model=cp_model.CpModel(),
            crew_ids=crew_ids,
            start_days=[day.toordinal() for day in domain.work_calendar.work_day_list],
            crew_intervals={index: [] for index in range(len(crew_ids))},
        )

        for job in domain.jobs:
            self._add_job_variables(state, domain, job)
            self._add_date_penalties(state, job)
        self._add_strict_crew_non_overlap(state)
        self._add_pair_penalties(state, domain.jobs)
        hard, soft, components, hard_weight = self._add_objective(state)

        validation_error = state.model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        return CotMaintenanceSchedule(
            model=state.model,
            crew_variables=state.crew_variables,
            start_variables=state.start_variables,
            crew_ids=crew_ids,
            hard_penalty=hard,
            soft_penalty=soft,
            penalty_components=components,
            hard_weight=hard_weight,
            mode=self.mode,
        )

    def _add_job_variables(
        self, state: _ModelState, domain: MaintenanceSchedule, job: Job
    ) -> None:
        model = state.model
        jid = job.job_id
        ends = [
            domain.work_calendar.end_date(index, job.duration_in_days).toordinal()
            for index in range(len(state.start_days))
        ]
        state.end_rows[jid] = ends
        crew = model.new_int_var(0, len(state.crew_ids) - 1, f"crew_{jid}")
        if self.mode == "strict":
            # Hard date limits restrict the choice of start workday.
            allowed_starts = [
                index
                for index, (start_day, end_day) in enumerate(
                    zip(state.start_days, ends)
                )
                if (
                    job.min_start_date is None
                    or start_day >= job.min_start_date.toordinal()
                )
                and (
                    job.max_end_date is None or end_day <= job.max_end_date.toordinal()
                )
            ]
            if not allowed_starts:
                model.add_bool_or([])
            start_index = model.new_int_var_from_domain(
                cp_model.Domain.from_values(allowed_starts or [0]),
                f"start_id_{jid}",
            )
        else:
            start_index = model.new_int_var(
                0, len(state.start_days) - 1, f"start_id_{jid}"
            )
        start = model.new_int_var(
            min(state.start_days), max(state.start_days), f"start_date_{jid}"
        )
        end = model.new_int_var(min(ends), max(ends), f"end_date_{jid}")
        # The workday choice determines both calendar dates.
        model.add_element(start_index, state.start_days, start)
        model.add_element(start_index, ends, end)
        state.crew_variables[jid] = crew
        state.start_variables[jid] = start_index
        state.start_dates[jid] = start
        state.end_dates[jid] = end

        if self.mode == "strict":
            # Each job occupies an interval only on its selected crew.
            selected_crews = [
                model.new_bool_var(f"on_crew_{jid}_{crew_id}")
                for crew_id in state.crew_ids
            ]
            model.add_map_domain(crew, selected_crews)
            span = model.new_int_var(
                1, max(ends) - min(state.start_days), f"calendar_span_{jid}"
            )
            model.add(span == end - start)
            for index, selected in enumerate(selected_crews):
                state.crew_intervals[index].append(
                    model.new_optional_interval_var(
                        start, span, end, selected, f"job_{jid}_crew_{index}"
                    )
                )

    def _add_date_penalties(self, state: _ModelState, job: Job) -> None:
        model = state.model
        jid = job.job_id
        start = state.start_dates[jid]
        end = state.end_dates[jid]
        ends = state.end_rows[jid]

        if job.min_start_date is not None:
            bound = max(0, job.min_start_date.toordinal() - min(state.start_days))
            penalty = model.new_int_var(0, bound, f"early_start_{jid}")
            model.add_max_equality(penalty, [0, job.min_start_date.toordinal() - start])
            state.terms["early_start_penalty"].append(penalty)
            state.bounds["early_start_penalty"] += bound
            if self.mode == "strict":
                model.add(start >= job.min_start_date.toordinal())

        if job.max_end_date is not None:
            bound = max(0, max(ends) - job.max_end_date.toordinal())
            penalty = model.new_int_var(0, bound, f"late_end_{jid}")
            model.add_max_equality(penalty, [0, end - job.max_end_date.toordinal()])
            state.terms["late_end_penalty"].append(penalty)
            state.bounds["late_end_penalty"] += bound
            if self.mode == "strict":
                model.add(end <= job.max_end_date.toordinal())

        if job.ideal_end_date is not None:
            ideal = job.ideal_end_date.toordinal()
            before = model.new_bool_var(f"before_ideal_{jid}")
            after = model.new_bool_var(f"after_ideal_{jid}")
            model.add(end < ideal).only_enforce_if(before)
            model.add(end >= ideal).only_enforce_if(before.negated())
            model.add(end > ideal).only_enforce_if(after)
            model.add(end <= ideal).only_enforce_if(after.negated())
            state.terms["before_ideal_penalty"].append(before)
            state.terms["after_ideal_penalty"].append(1_000_000 * after)
            state.bounds["before_ideal_penalty"] += 1
            state.bounds["after_ideal_penalty"] += 1_000_000

    def _add_strict_crew_non_overlap(self, state: _ModelState) -> None:
        if self.mode == "strict":
            for intervals in state.crew_intervals.values():
                if intervals:
                    state.model.add_no_overlap(intervals)

    def _add_pair_penalties(self, state: _ModelState, jobs: list[Job]) -> None:
        if not jobs:
            return
        model = state.model
        earliest_start = min(state.start_days)
        latest_start = max(state.start_days)
        for first, second in combinations(jobs, 2):
            a, b = first.job_id, second.job_id
            ends_a, ends_b = state.end_rows[a], state.end_rows[b]
            earliest_pair_end = min(min(ends_a), min(ends_b))
            latest_pair_end = min(max(ends_a), max(ends_b))
            lower_raw = earliest_pair_end - latest_start
            upper_raw = latest_pair_end - earliest_start
            positive_bound = max(0, upper_raw)
            min_end = model.new_int_var(
                earliest_pair_end,
                latest_pair_end,
                f"min_end_{a}_{b}",
            )
            max_start = model.new_int_var(
                earliest_start, latest_start, f"max_start_{a}_{b}"
            )
            raw = model.new_int_var(lower_raw, upper_raw, f"raw_overlap_{a}_{b}")
            positive = model.new_int_var(0, positive_bound, f"positive_overlap_{a}_{b}")
            model.add_min_equality(min_end, [state.end_dates[a], state.end_dates[b]])
            model.add_max_equality(
                max_start, [state.start_dates[a], state.start_dates[b]]
            )
            model.add(raw == min_end - max_start)
            model.add_max_equality(positive, [0, raw])
            same_crew = model.new_bool_var(f"same_crew_{a}_{b}")
            model.add(
                state.crew_variables[a] == state.crew_variables[b]
            ).only_enforce_if(same_crew)
            model.add(
                state.crew_variables[a] != state.crew_variables[b]
            ).only_enforce_if(same_crew.negated())

            # The source scorer visited both orders, so each pair counts twice.
            hard_pair = model.new_int_var(
                0, 2 * positive_bound, f"crew_overlap_{a}_{b}"
            )
            model.add(hard_pair == 2 * positive).only_enforce_if(same_crew)
            model.add(hard_pair == 0).only_enforce_if(same_crew.negated())
            state.terms["crew_overlap_penalty"].append(hard_pair)
            state.bounds["crew_overlap_penalty"] += 2 * positive_bound

            common_tags = len(set(first.tags) & set(second.tags))
            if common_tags:
                # abs(raw) also charges separated same-crew jobs with shared tags.
                absolute_bound = max(abs(lower_raw), abs(upper_raw))
                absolute = model.new_int_var(
                    0, absolute_bound, f"absolute_overlap_{a}_{b}"
                )
                model.add_abs_equality(absolute, raw)
                coefficient = 2_000 * common_tags
                tag_pair = model.new_int_var(
                    0, coefficient * absolute_bound, f"tag_penalty_{a}_{b}"
                )
                model.add(tag_pair == coefficient * absolute).only_enforce_if(same_crew)
                model.add(tag_pair == 0).only_enforce_if(same_crew.negated())
                state.terms["tag_penalty"].append(tag_pair)
                state.bounds["tag_penalty"] += coefficient * absolute_bound

    def _add_objective(
        self, state: _ModelState
    ) -> tuple[cp_model.IntVar, cp_model.IntVar, dict[str, cp_model.IntVar], int]:
        model = state.model
        hard_names = ("crew_overlap_penalty", "early_start_penalty", "late_end_penalty")
        soft_names = ("before_ideal_penalty", "after_ideal_penalty", "tag_penalty")
        hard_bound = sum(state.bounds[name] for name in hard_names)
        soft_bound = sum(state.bounds[name] for name in soft_names)
        # One hard point must outweigh every possible change in the soft score.
        hard_weight = soft_bound + 1
        safe_bound = cp_model.INT_MAX // 2
        if any(
            value > safe_bound
            for value in (
                *state.bounds.values(),
                hard_bound,
                soft_bound,
                hard_weight,
                hard_weight * hard_bound + soft_bound,
            )
        ):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")

        components = {}
        for name, expressions in state.terms.items():
            component = model.new_int_var(0, state.bounds[name], name)
            model.add(component == sum(expressions))
            components[name] = component
        hard = model.new_int_var(0, hard_bound, "hard_penalty")
        soft = model.new_int_var(0, soft_bound, "soft_penalty")
        model.add(hard == sum(components[name] for name in hard_names))
        model.add(soft == sum(components[name] for name in soft_names))
        if self.mode == "strict":
            model.add(hard == 0)
            model.minimize(soft)
        else:
            model.minimize(hard_weight * hard + soft)
        return hard, soft, components, hard_weight
