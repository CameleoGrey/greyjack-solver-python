from itertools import combinations

from ortools.sat.python import cp_model

from ..cotwin import CotMaintenanceSchedule
from ..domain import MaintenanceSchedule


class CotwinBuilder:
    """Encode the original hard/soft score in integer CP-SAT constraints."""

    def __init__(self, *, mode: str = "strict") -> None:
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode

    def build_cotwin(self, domain: MaintenanceSchedule) -> CotMaintenanceSchedule:
        domain.validate()
        model = cp_model.CpModel()
        jobs = domain.jobs
        crew_ids = tuple(crew.crew_id for crew in domain.crews)
        workdays = domain.work_calendar.work_day_list
        start_days = [day.toordinal() for day in workdays]
        terms: dict[str, list] = {
            "crew_overlap_penalty": [],
            "early_start_penalty": [],
            "late_end_penalty": [],
            "before_ideal_penalty": [],
            "after_ideal_penalty": [],
            "tag_penalty": [],
        }
        bounds = dict.fromkeys(terms, 0)
        crew_variables = {}
        start_variables = {}
        start_dates = {}
        end_dates = {}
        end_rows = {}
        crew_intervals = {index: [] for index in range(len(crew_ids))}

        for job in jobs:
            jid = job.job_id
            ends = [
                domain.work_calendar.end_date(index, job.duration_in_days).toordinal()
                for index in range(len(workdays))
            ]
            end_rows[jid] = ends
            crew = model.new_int_var(0, len(crew_ids) - 1, f"crew_{jid}")
            if self.mode == "strict":
                allowed_starts = [
                    index
                    for index, (start_day, end_day) in enumerate(zip(start_days, ends))
                    if (
                        job.min_start_date is None
                        or start_day >= job.min_start_date.toordinal()
                    )
                    and (
                        job.max_end_date is None
                        or end_day <= job.max_end_date.toordinal()
                    )
                ]
                if not allowed_starts:
                    model.add_bool_or([])
                start_index = model.new_int_var_from_domain(
                    cp_model.Domain.from_values(allowed_starts or [0]),
                    f"start_id_{jid}",
                )
            else:
                start_index = model.new_int_var(0, len(workdays) - 1, f"start_id_{jid}")
            start = model.new_int_var(
                min(start_days), max(start_days), f"start_date_{jid}"
            )
            end = model.new_int_var(min(ends), max(ends), f"end_date_{jid}")
            model.add_element(start_index, start_days, start)
            model.add_element(start_index, ends, end)
            crew_variables[jid] = crew
            start_variables[jid] = start_index
            start_dates[jid] = start
            end_dates[jid] = end

            if self.mode == "strict":
                selected_crews = [
                    model.new_bool_var(f"on_crew_{jid}_{crew_id}")
                    for crew_id in crew_ids
                ]
                model.add_map_domain(crew, selected_crews)
                span = model.new_int_var(
                    1, max(ends) - min(start_days), f"calendar_span_{jid}"
                )
                model.add(span == end - start)
                for index, selected in enumerate(selected_crews):
                    crew_intervals[index].append(
                        model.new_optional_interval_var(
                            start, span, end, selected, f"job_{jid}_crew_{index}"
                        )
                    )

            if job.min_start_date is not None:
                bound = max(0, job.min_start_date.toordinal() - min(start_days))
                penalty = model.new_int_var(0, bound, f"early_start_{jid}")
                model.add_max_equality(
                    penalty, [0, job.min_start_date.toordinal() - start]
                )
                terms["early_start_penalty"].append(penalty)
                bounds["early_start_penalty"] += bound
                if self.mode == "strict":
                    model.add(start >= job.min_start_date.toordinal())
            if job.max_end_date is not None:
                bound = max(0, max(ends) - job.max_end_date.toordinal())
                penalty = model.new_int_var(0, bound, f"late_end_{jid}")
                model.add_max_equality(penalty, [0, end - job.max_end_date.toordinal()])
                terms["late_end_penalty"].append(penalty)
                bounds["late_end_penalty"] += bound
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
                terms["before_ideal_penalty"].append(before)
                terms["after_ideal_penalty"].append(1_000_000 * after)
                bounds["before_ideal_penalty"] += 1
                bounds["after_ideal_penalty"] += 1_000_000

        if self.mode == "strict":
            for intervals in crew_intervals.values():
                if intervals:
                    model.add_no_overlap(intervals)

        if jobs:
            earliest_start = min(start_days)
            latest_start = max(start_days)
        for first, second in combinations(jobs, 2):
            a, b = first.job_id, second.job_id
            lower_raw = min(min(end_rows[a]), min(end_rows[b])) - latest_start
            upper_raw = min(max(end_rows[a]), max(end_rows[b])) - earliest_start
            positive_bound = max(0, upper_raw)
            min_end = model.new_int_var(
                min(min(end_rows[a]), min(end_rows[b])),
                min(max(end_rows[a]), max(end_rows[b])),
                f"min_end_{a}_{b}",
            )
            max_start = model.new_int_var(
                earliest_start, latest_start, f"max_start_{a}_{b}"
            )
            raw = model.new_int_var(lower_raw, upper_raw, f"raw_overlap_{a}_{b}")
            positive = model.new_int_var(0, positive_bound, f"positive_overlap_{a}_{b}")
            model.add_min_equality(min_end, [end_dates[a], end_dates[b]])
            model.add_max_equality(max_start, [start_dates[a], start_dates[b]])
            model.add(raw == min_end - max_start)
            model.add_max_equality(positive, [0, raw])
            same_crew = model.new_bool_var(f"same_crew_{a}_{b}")
            model.add(crew_variables[a] == crew_variables[b]).only_enforce_if(same_crew)
            model.add(crew_variables[a] != crew_variables[b]).only_enforce_if(
                same_crew.negated()
            )
            hard_pair = model.new_int_var(
                0, 2 * positive_bound, f"crew_overlap_{a}_{b}"
            )
            model.add(hard_pair == 2 * positive).only_enforce_if(same_crew)
            model.add(hard_pair == 0).only_enforce_if(same_crew.negated())
            terms["crew_overlap_penalty"].append(hard_pair)
            bounds["crew_overlap_penalty"] += 2 * positive_bound

            common_tags = len(set(first.tags) & set(second.tags))
            if common_tags:
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
                terms["tag_penalty"].append(tag_pair)
                bounds["tag_penalty"] += coefficient * absolute_bound

        hard_names = ("crew_overlap_penalty", "early_start_penalty", "late_end_penalty")
        soft_names = ("before_ideal_penalty", "after_ideal_penalty", "tag_penalty")
        hard_bound = sum(bounds[name] for name in hard_names)
        soft_bound = sum(bounds[name] for name in soft_names)
        hard_weight = soft_bound + 1
        safe_bound = cp_model.INT_MAX // 2
        if any(
            value > safe_bound
            for value in (
                *bounds.values(),
                hard_bound,
                soft_bound,
                hard_weight,
                hard_weight * hard_bound + soft_bound,
            )
        ):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")

        components = {}
        for name, expressions in terms.items():
            component = model.new_int_var(0, bounds[name], name)
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
        validation_error = model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        return CotMaintenanceSchedule(
            model=model,
            crew_variables=crew_variables,
            start_variables=start_variables,
            crew_ids=crew_ids,
            hard_penalty=hard,
            soft_penalty=soft,
            penalty_components=components,
            hard_weight=hard_weight,
            mode=self.mode,
        )
