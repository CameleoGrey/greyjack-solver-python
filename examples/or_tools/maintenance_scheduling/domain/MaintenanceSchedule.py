from dataclasses import dataclass, field
from datetime import date, datetime
from itertools import combinations
from typing import Any

from .Crew import Crew
from .Job import Job
from .WorkCalendar import WorkCalendar


@dataclass
class MaintenanceSchedule:
    work_calendar: WorkCalendar
    crews: list[Crew] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)

    def validate(self) -> None:
        if not isinstance(self.work_calendar, WorkCalendar):
            raise ValueError("Schedule requires a work calendar")
        for kind, items, field_name in (
            ("crew", self.crews, "crew_id"),
            ("job", self.jobs, "job_id"),
        ):
            seen = set()
            for item in items:
                item_id = getattr(item, field_name)
                if type(item_id) is not int or item_id in seen:
                    raise ValueError(f"Invalid or duplicate {kind} ID: {item_id!r}")
                seen.add(item_id)
                if not isinstance(item.name, str):
                    raise ValueError(f"{kind.capitalize()} {item_id} needs a name")
        if self.jobs and (not self.crews or not self.work_calendar.work_day_list):
            raise ValueError("Jobs require crews and workdays")
        crew_ids = {crew.crew_id for crew in self.crews}
        workday_count = len(self.work_calendar.work_day_list)
        for job in self.jobs:
            if type(job.duration_in_days) is not int or job.duration_in_days < 1:
                raise ValueError(f"Job {job.job_id} needs a positive workday duration")
            for label in ("min_start_date", "max_end_date", "ideal_end_date"):
                value = getattr(job, label)
                if value is not None and (
                    not isinstance(value, date) or isinstance(value, datetime)
                ):
                    raise ValueError(f"Job {job.job_id} {label} must be a date")
            if (
                not isinstance(job.tags, (list, tuple, set))
                or any(not isinstance(tag, str) for tag in job.tags)
                or len(job.tags) != len(set(job.tags))
            ):
                raise ValueError(f"Job {job.job_id} needs unique string tags")
            if job.crew_id is not None and (
                type(job.crew_id) is not int or job.crew_id not in crew_ids
            ):
                raise ValueError(f"Job {job.job_id} references an unknown crew")
            if job.start_date_id is not None and (
                type(job.start_date_id) is not int
                or not 0 <= job.start_date_id < workday_count
            ):
                raise ValueError(f"Job {job.job_id} has an invalid start workday")
            # Check dates used by the model before constructing any variables.
            if workday_count:
                self.work_calendar.end_date(workday_count - 1, job.duration_in_days)

    def calculate_metrics(self) -> dict[str, Any]:
        """Score business assignments without using the CP-SAT cotwin."""
        self.validate()
        components = {
            "crew_overlap_penalty": 0,
            "early_start_penalty": 0,
            "late_end_penalty": 0,
            "before_ideal_penalty": 0,
            "after_ideal_penalty": 0,
            "tag_penalty": 0,
        }
        scheduled = []
        for job in self.jobs:
            if job.crew_id is None or job.start_date_id is None:
                raise ValueError(f"Job {job.job_id} is unassigned")
            start = self.work_calendar.work_day_list[job.start_date_id]
            end = self.work_calendar.end_date(job.start_date_id, job.duration_in_days)
            scheduled.append((job, start, end))
            if job.min_start_date is not None:
                components["early_start_penalty"] += max(
                    0, (job.min_start_date - start).days
                )
            if job.max_end_date is not None:
                components["late_end_penalty"] += max(0, (end - job.max_end_date).days)
            if job.ideal_end_date is not None:
                components["before_ideal_penalty"] += int(end < job.ideal_end_date)
                components["after_ideal_penalty"] += 1_000_000 * int(
                    end > job.ideal_end_date
                )
        for (first, start_a, end_a), (second, start_b, end_b) in combinations(
            scheduled, 2
        ):
            if first.crew_id != second.crew_id:
                continue
            raw_overlap = (min(end_a, end_b) - max(start_a, start_b)).days
            # The source loops over ordered pairs, hence both factors of two.
            components["crew_overlap_penalty"] += 2 * max(0, raw_overlap)
            components["tag_penalty"] += (
                2 * 1_000 * len(set(first.tags) & set(second.tags)) * abs(raw_overlap)
            )
        hard = sum(
            components[name]
            for name in (
                "crew_overlap_penalty",
                "early_start_penalty",
                "late_end_penalty",
            )
        )
        soft = sum(
            components[name]
            for name in ("before_ideal_penalty", "after_ideal_penalty", "tag_penalty")
        )
        return {
            **components,
            "hard_penalty": hard,
            "soft_penalty": soft,
            "business_feasible": hard == 0,
        }

    def print_schedule(self) -> None:
        self.validate()
        names = {crew.crew_id: crew.name for crew in self.crews}
        for job in self.jobs:
            if job.crew_id is None or job.start_date_id is None:
                raise ValueError(f"Job {job.job_id} is unassigned")
            start = self.work_calendar.work_day_list[job.start_date_id]
            end = self.work_calendar.end_date(job.start_date_id, job.duration_in_days)
            print(
                f"Job {job.job_id}: {job.name} | crew {job.crew_id} "
                f"({names[job.crew_id]}) | {start} to {end} | "
                f"duration {job.duration_in_days} workdays | tags {job.tags}"
            )

    def print_metrics(self) -> None:
        for name, value in self.calculate_metrics().items():
            print(f"{name}: {value}")
