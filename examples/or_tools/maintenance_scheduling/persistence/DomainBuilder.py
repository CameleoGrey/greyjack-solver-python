from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime, timedelta

from ..domain import MaintenanceSchedule
from ..solver.MaintenanceSchedulingSolution import MaintenanceSchedulingSolution
from .DemoDataGenerator import generate_demo_data


class DomainBuilder:
    """Build source-compatible demo data and reconstruct independent results."""

    def __init__(
        self, dataset_size: str = "small", start_date: date | None = None
    ) -> None:
        if dataset_size not in ("small", "large"):
            raise ValueError('dataset_size must be "small" or "large"')
        if start_date is not None and (
            not isinstance(start_date, date) or isinstance(start_date, datetime)
        ):
            raise ValueError("start_date must be a date-only value")
        self.dataset_size = dataset_size
        today = date.today()
        self.start_date = (
            today + timedelta(days=(7 - today.weekday()) % 7)
            if start_date is None
            else start_date
        )

    def build_domain_from_scratch(self) -> MaintenanceSchedule:
        try:
            return generate_demo_data(self.dataset_size, self.start_date)
        except OverflowError as error:
            raise ValueError("start_date leaves insufficient calendar range") from error

    def build_from_domain(self, domain: MaintenanceSchedule) -> MaintenanceSchedule:
        domain.validate()
        return deepcopy(domain)

    def build_from_solution(
        self,
        solution: MaintenanceSchedulingSolution,
        initial_domain: MaintenanceSchedule | None = None,
    ) -> MaintenanceSchedule:
        if not solution.has_solution:
            raise ValueError("Cannot reconstruct a result without an incumbent")
        domain = (
            self.build_domain_from_scratch()
            if initial_domain is None
            else self.build_from_domain(initial_domain)
        )
        if not isinstance(solution.assignments, Mapping) or set(
            solution.assignments
        ) != {job.job_id for job in domain.jobs}:
            raise ValueError("Solution must cover exactly the domain's job IDs")
        crews = {crew.crew_id for crew in domain.crews}
        for job in domain.jobs:
            assignment = solution.assignments[job.job_id]
            if (
                not isinstance(assignment, tuple)
                or len(assignment) != 2
                or type(assignment[0]) is not int
                or type(assignment[1]) is not int
                or assignment[0] not in crews
                or not 0 <= assignment[1] < len(domain.work_calendar.work_day_list)
            ):
                raise ValueError(f"Job {job.job_id} has an invalid assignment")
            job.crew_id, job.start_date_id = assignment
        if (
            type(solution.hard_penalty) is not int
            or type(solution.soft_penalty) is not int
        ):
            raise ValueError("Solution scores must be integers")
        metrics = domain.calculate_metrics()
        if (metrics["hard_penalty"], metrics["soft_penalty"]) != (
            solution.hard_penalty,
            solution.soft_penalty,
        ):
            raise ValueError("Reconstructed domain scores do not match solver result")
        if solution.mode == "strict" and metrics["hard_penalty"]:
            raise ValueError("Strict result violates a hard scheduling rule")
        return domain
