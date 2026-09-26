from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any

from .Job import Job
from .Line import Line
from .Product import Product


def _minute_aligned(value: datetime | timedelta, label: str) -> None:
    if isinstance(value, datetime):
        valid = value.tzinfo is None and value.second == value.microsecond == 0
    elif isinstance(value, timedelta):
        valid = value.total_seconds() % 60 == 0
    else:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be minute-aligned and timezone-naive")


@dataclass
class PackagingSchedule:
    products: list[Product] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)

    def validate(self) -> None:
        for name, items in (
            ("product", self.products),
            ("line", self.lines),
            ("job", self.jobs),
        ):
            ids = set()
            for item in items:
                if type(item.id) is not int or item.id in ids:
                    raise ValueError(f"Invalid or duplicate {name} ID: {item.id!r}")
                ids.add(item.id)
        if self.jobs and not self.lines:
            raise ValueError("Cannot schedule jobs without lines")
        products = {id(product) for product in self.products}
        lines = {id(line) for line in self.lines}
        jobs = {id(job) for job in self.jobs}
        for product in self.products:
            if not isinstance(product.name, str):
                raise ValueError(f"Product {product.id} name must be a string")
            if {id(item) for item in product.cleaning_durations} != products:
                raise ValueError(f"Product {product.id} lacks a complete cleaning map")
            for duration in product.cleaning_durations.values():
                _minute_aligned(duration, "Cleaning duration")
                if duration < timedelta(0):
                    raise ValueError("Cleaning duration must be nonnegative")
        for line in self.lines:
            if not isinstance(line.name, str) or not isinstance(line.operator, str):
                raise ValueError(f"Line {line.id} name and operator must be strings")
            _minute_aligned(line.start_date_time, f"Line {line.id} start")
            if any(id(job) not in jobs for job in line.jobs):
                raise ValueError(f"Line {line.id} references unknown job")
        for job in self.jobs:
            if not isinstance(job.name, str) or id(job.product) not in products:
                raise ValueError(f"Job {job.id} has invalid name or product")
            _minute_aligned(job.duration, f"Job {job.id} duration")
            if job.duration <= timedelta(0):
                raise ValueError(f"Job {job.id} duration must be positive")
            for label in ("min_start_time", "ideal_end_time", "max_end_time"):
                _minute_aligned(getattr(job, label), f"Job {job.id} {label}")
            if type(job.priority) is not int or job.priority < 0:
                raise ValueError(f"Job {job.id} priority must be nonnegative")
            if type(job.pinned) is not bool:
                raise ValueError(f"Job {job.id} pinned must be boolean")
            if job.pinned:
                raise ValueError("Pinned jobs are not supported by the source example")
            if job.line is not None and id(job.line) not in lines:
                raise ValueError(f"Job {job.id} references unknown line")
            for label in ("start_time", "end_time"):
                value = getattr(job, label)
                if value is not None:
                    _minute_aligned(value, f"Job {job.id} {label}")

    def calculate_metrics(self) -> dict[str, Any]:
        """Independently replay ordered business lines and actual production times."""
        self.validate()
        seen = set()
        late_minutes = 0
        early_minutes = 0
        ideal_minutes = 0
        cleaning_penalty = 0
        cleaning_minutes = 0
        line_spans = {}
        for line in self.lines:
            previous = None
            for job in line.jobs:
                if id(job) in seen:
                    raise ValueError(f"Job {job.id} appears more than once")
                seen.add(id(job))
                if job.line is not line:
                    raise ValueError(f"Job {job.id} has inconsistent line assignment")
                if job.start_time is None or job.end_time is None:
                    raise ValueError(f"Job {job.id} has no production times")
                if job.end_time != job.start_time + job.duration:
                    raise ValueError(f"Job {job.id} has incorrect production end")
                if previous is None:
                    if job.start_time < line.start_date_time:
                        raise ValueError(f"Job {job.id} precedes line start")
                else:
                    cleanup = job.product.get_cleanup_duration(previous.product)
                    minutes = int(cleanup.total_seconds() // 60)
                    cleaning_minutes += minutes
                    cleaning_penalty += job.priority * minutes
                    if job.start_time < previous.end_time + cleanup:
                        raise ValueError(f"Job {job.id} violates cleaning precedence")
                late_minutes += max(
                    0, int((job.end_time - job.max_end_time).total_seconds() // 60)
                )
                early_minutes += max(
                    0, int((job.min_start_time - job.start_time).total_seconds() // 60)
                )
                ideal_minutes += max(
                    0, int((job.end_time - job.ideal_end_time).total_seconds() // 60)
                )
                previous = job
            line_spans[line.id] = (
                int((previous.end_time - line.start_date_time).total_seconds() // 60)
                if previous is not None
                else 0
            )
        if seen != {id(job) for job in self.jobs}:
            raise ValueError("Schedule must contain every job exactly once")

        operator_overlap = 0
        for left, right in combinations(self.jobs, 2):
            if left.line.operator != right.line.operator:
                continue
            overlap = min(left.end_time, right.end_time) - max(
                left.start_time, right.start_time
            )
            operator_overlap += max(0, int(overlap.total_seconds() // 60))
        medium_penalty = sum(span * span for span in line_spans.values())
        soft_penalty = operator_overlap + ideal_minutes + cleaning_penalty
        return {
            "hard_penalty": late_minutes,
            "medium_penalty": medium_penalty,
            "soft_penalty": soft_penalty,
            "late_minutes": late_minutes,
            "early_start_minutes": early_minutes,
            "ideal_lateness_minutes": ideal_minutes,
            "operator_overlap_minutes": operator_overlap,
            "cleaning_minutes": cleaning_minutes,
            "cleaning_penalty": cleaning_penalty,
            "line_spans_minutes": line_spans,
            "strict_feasible": late_minutes == early_minutes == operator_overlap == 0,
        }

    def print_schedule(self) -> None:
        for line in self.lines:
            print("#" * 54)
            print(line)

    def print_metrics(self) -> None:
        metrics = self.calculate_metrics()
        for name in (
            "late_minutes",
            "early_start_minutes",
            "ideal_lateness_minutes",
            "operator_overlap_minutes",
            "cleaning_minutes",
            "cleaning_penalty",
            "hard_penalty",
            "medium_penalty",
            "soft_penalty",
            "strict_feasible",
        ):
            print(f"{name}: {metrics[name]}")
