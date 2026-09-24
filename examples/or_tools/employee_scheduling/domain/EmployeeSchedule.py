from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import combinations
from math import isqrt, sqrt
from typing import Any

from .Employee import Employee
from .Shift import Shift


@dataclass
class EmployeeSchedule:
    employees: list[Employee]
    shifts: list[Shift]

    def validate(self) -> None:
        """Validate business data, permitting shifts that are still unassigned."""
        for employee_index, employee in enumerate(self.employees):
            if not isinstance(employee.skills, (list, tuple, set, frozenset)) or any(
                not isinstance(skill, str) for skill in employee.skills
            ):
                raise ValueError(f"Employee {employee_index} skills must be strings")
            for field_name in (
                "unavailable_dates",
                "undesired_dates",
                "desired_dates",
            ):
                values = getattr(employee, field_name)
                if not isinstance(values, (list, tuple, set, frozenset)) or any(
                    not isinstance(value, date) or isinstance(value, datetime)
                    for value in values
                ):
                    raise ValueError(
                        f"Employee {employee_index} {field_name} must contain "
                        "date-only values"
                    )

        if self.shifts and not self.employees:
            raise ValueError("Cannot assign shifts without any employees")

        shift_ids = set()
        for shift in self.shifts:
            if type(shift.id) is not int:
                raise ValueError(f"Shift ID must be an integer; got {shift.id!r}")
            if shift.id in shift_ids:
                raise ValueError(f"Duplicate shift ID: {shift.id}")
            shift_ids.add(shift.id)
            for field_name in ("start", "end"):
                value = getattr(shift, field_name)
                if (
                    not isinstance(value, datetime)
                    or value.tzinfo is not None
                    or value.second != 0
                    or value.microsecond != 0
                ):
                    raise ValueError(
                        f"Shift {shift.id} {field_name} must be a naive, "
                        "minute-aligned datetime"
                    )
            if shift.end <= shift.start:
                raise ValueError(f"Shift {shift.id} end must be after start")
            if not isinstance(shift.required_skill, str):
                raise ValueError(f"Shift {shift.id} required_skill must be a string")
            if shift.employee is not None and (
                type(shift.employee) is not int
                or not 0 <= shift.employee < len(self.employees)
            ):
                raise ValueError(
                    f"Shift {shift.id} references unknown employee index "
                    f"{shift.employee!r}"
                )

    def calculate_metrics(self) -> dict[str, Any]:
        """Independently score complete assignments in business objects.

        The original scoring visits both orders of every same-employee pair.
        This implementation visits each unordered pair once and doubles its
        contribution, retaining overlap/rest minutes and same-start-day rules.
        """
        self.validate()
        skill_penalty = 0
        unavailable_penalty = 0
        overlapping_penalty = 0
        unrelax_penalty = 0
        many_shifts_per_day_penalty = 0
        undesired_date_penalty = 0
        desired_date_reward = 0
        shift_counts = [0] * len(self.employees)
        assigned_shifts: list[list[Shift]] = [[] for _ in self.employees]

        for shift in self.shifts:
            if shift.employee is None:
                raise ValueError(f"Shift {shift.id} is unassigned")
            employee = self.employees[shift.employee]
            shift_counts[shift.employee] += 1
            assigned_shifts[shift.employee].append(shift)
            start_date = shift.start.date()
            skill_penalty += int(shift.required_skill not in employee.skills)
            unavailable_penalty += int(start_date in employee.unavailable_dates)
            undesired_date_penalty += int(start_date in employee.undesired_dates)
            desired_date_reward -= int(start_date in employee.desired_dates)

        minute = timedelta(minutes=1)
        for employee_shifts in assigned_shifts:
            for left, right in combinations(employee_shifts, 2):
                overlap = min(left.end, right.end) - max(left.start, right.start)
                if overlap > timedelta(0):
                    overlapping_penalty += 2 * (overlap // minute)
                else:
                    gap = max(left.start, right.start) - min(left.end, right.end)
                    unrelax_penalty += 2 * max(0, 600 - gap // minute)
                if left.start.date() == right.start.date():
                    many_shifts_per_day_penalty += 2

        employee_count = len(self.employees)
        shift_count = len(self.shifts)
        mean_shift_count = shift_count / employee_count if employee_count else 0.0
        q = employee_count * sum(count * count for count in shift_counts)
        q -= shift_count * shift_count
        unfairness_penalty = sqrt(q / employee_count) if employee_count else 0.0
        fairness_cents = isqrt(10_000 * q // employee_count) if employee_count else 0
        hard_penalty = (
            skill_penalty
            + unavailable_penalty
            + overlapping_penalty
            + unrelax_penalty
            + many_shifts_per_day_penalty
        )
        soft_penalty_cents = (
            100 * (undesired_date_penalty + desired_date_reward) + fairness_cents
        )
        return {
            "skill_penalty": skill_penalty,
            "unavailable_penalty": unavailable_penalty,
            "overlapping_penalty": overlapping_penalty,
            "unrelax_penalty": unrelax_penalty,
            "many_shifts_per_day_penalty": many_shifts_per_day_penalty,
            "undesired_date_penalty": undesired_date_penalty,
            "desired_date_reward": desired_date_reward,
            "unfairness_penalty": unfairness_penalty,
            "fairness_cents": fairness_cents,
            "hard_penalty": hard_penalty,
            "soft_penalty_cents": soft_penalty_cents,
            "shift_counts": shift_counts,
            "mean_shift_count": mean_shift_count,
            "business_feasible": hard_penalty == 0,
        }

    def print_schedule(self) -> None:
        self.validate()
        for shift in self.shifts:
            employee = (
                "Unassigned"
                if shift.employee is None
                else str(self.employees[shift.employee])
            )
            print(f"{shift} --> {employee}")

    def print_metrics(self) -> None:
        metrics = self.calculate_metrics()
        for employee, count in zip(self.employees, metrics["shift_counts"]):
            print(f"{employee.name} shifts count: {count}")
        print(f"Mean shifts count: {metrics['mean_shift_count']}")
        print(f"Skill penalty: {metrics['skill_penalty']}")
        print(f"Unavailable penalty: {metrics['unavailable_penalty']}")
        print(f"Overlapping penalty (minutes): {metrics['overlapping_penalty']}")
        print(f"Insufficient rest penalty (minutes): {metrics['unrelax_penalty']}")
        print(f"Many shifts per day penalty: {metrics['many_shifts_per_day_penalty']}")
        print(f"Undesired date penalty: {metrics['undesired_date_penalty']}")
        print(f"Desired date reward: {metrics['desired_date_reward']}")
        print(f"Unfairness penalty: {metrics['unfairness_penalty']}")
        print(f"Fairness cents (floored): {metrics['fairness_cents']}")
        print(f"Hard penalty: {metrics['hard_penalty']}")
        print(f"Soft penalty cents: {metrics['soft_penalty_cents']}")
        soft_cents = metrics["soft_penalty_cents"]
        soft_sign = "-" if soft_cents < 0 else ""
        print(
            f"Soft penalty: {soft_sign}{abs(soft_cents) // 100}."
            f"{abs(soft_cents) % 100:02d}"
        )
        print(f"Business feasible: {metrics['business_feasible']}")
