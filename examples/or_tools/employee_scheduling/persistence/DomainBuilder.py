from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime
from typing import Any

from ..domain import EmployeeSchedule
from .demo_data import (
    DemoData,
    earliest_monday_on_or_after,
    generate_demo_data,
    parameters_for,
)


class DomainBuilder:
    """Create repeatable data and reconstruct independent business assignments."""

    def __init__(
        self,
        random_seed: int = 45,
        dataset_size: str = "large",
        start_date: date | None = None,
    ) -> None:
        if type(random_seed) is not int:
            raise ValueError("random_seed must be an integer")
        if dataset_size not in ("small", "large"):
            raise ValueError('dataset_size must be "large" or "small"')
        if start_date is not None and (
            not isinstance(start_date, date) or isinstance(start_date, datetime)
        ):
            raise ValueError("start_date must be a date-only value")
        self.random_seed = random_seed
        self.dataset_size = dataset_size
        self.start_date = (
            earliest_monday_on_or_after(date.today())
            if start_date is None
            else start_date
        )

    def build_domain_from_scratch(self) -> EmployeeSchedule:
        parameters = parameters_for(
            DemoData(self.dataset_size.upper()), self.random_seed
        )
        try:
            domain = generate_demo_data(parameters, start_date=self.start_date)
        except OverflowError as error:
            raise ValueError(
                "start_date leaves insufficient calendar range for the generated schedule"
            ) from error
        domain.validate()
        return domain

    def build_from_domain(self, domain: EmployeeSchedule) -> EmployeeSchedule:
        return deepcopy(domain)

    def build_from_solution(
        self,
        solution: Any,
        initial_domain: EmployeeSchedule | None = None,
    ) -> EmployeeSchedule:
        """Apply stable shift IDs, then verify both independently rescored totals."""
        if not solution.has_solution:
            raise ValueError("Cannot reconstruct a solution without an incumbent")
        domain = (
            self.build_domain_from_scratch()
            if initial_domain is None
            else self.build_from_domain(initial_domain)
        )
        domain.validate()
        if (
            not isinstance(solution.assignments, Mapping)
            or any(type(shift_id) is not int for shift_id in solution.assignments)
            or set(solution.assignments) != {shift.id for shift in domain.shifts}
        ):
            raise ValueError(
                "Solution assignments must cover exactly the domain's shift IDs"
            )
        for shift in domain.shifts:
            employee_index = solution.assignments[shift.id]
            if type(employee_index) is not int or not 0 <= employee_index < len(
                domain.employees
            ):
                raise ValueError(
                    f"Shift {shift.id} references unknown employee index "
                    f"{employee_index!r}"
                )
            shift.employee = employee_index
        if (
            type(solution.hard_penalty) is not int
            or type(solution.soft_penalty_cents) is not int
        ):
            raise ValueError("Solution scores must be integers")
        metrics = domain.calculate_metrics()
        if (metrics["hard_penalty"], metrics["soft_penalty_cents"]) != (
            solution.hard_penalty,
            solution.soft_penalty_cents,
        ):
            raise ValueError(
                "Reconstructed domain scores do not match the solver result"
            )
        return domain
