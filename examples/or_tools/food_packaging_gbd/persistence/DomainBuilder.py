from copy import deepcopy
from datetime import date, datetime

from ..domain.PackagingSchedule import PackagingSchedule
from ..solver.FoodPackagingSolution import FoodPackagingSolution
from .DemoDataGenerator import DemoDataGenerator


class DomainBuilder:
    def __init__(
        self,
        line_count: int = 5,
        job_count: int = 100,
        *,
        seed: int = 37,
        start_date: date | None = None,
    ):
        generator = DemoDataGenerator(
            line_count, job_count, seed=seed, start_date=start_date
        )
        self.line_count = generator.line_count
        self.job_count = generator.job_count
        self.seed = generator.seed
        self.start_date = generator.start_date

    def build_domain_from_scratch(self) -> PackagingSchedule:
        return DemoDataGenerator(
            self.line_count,
            self.job_count,
            seed=self.seed,
            start_date=self.start_date,
        ).generate_demo_data()

    def build_from_domain(self, domain: PackagingSchedule) -> PackagingSchedule:
        domain.validate()
        return deepcopy(domain)

    def build_from_solution(
        self,
        solution: FoodPackagingSolution,
        initial_domain: PackagingSchedule | None = None,
    ) -> PackagingSchedule:
        if not solution.has_solution:
            raise ValueError(f"Cannot reconstruct status {solution.status}")
        domain = (
            self.build_domain_from_scratch()
            if initial_domain is None
            else self.build_from_domain(initial_domain)
        )
        jobs = {job.id: job for job in domain.jobs}
        lines = {line.id: line for line in domain.lines}
        if set(solution.line_routes) != set(lines):
            raise ValueError("Solution routes must cover exactly the domain's lines")
        all_job_ids = [
            job_id for route in solution.line_routes.values() for job_id in route
        ]
        if len(all_job_ids) != len(jobs) or set(all_job_ids) != set(jobs):
            raise ValueError("Solution routes must contain each job exactly once")
        if set(solution.start_times) != set(jobs):
            raise ValueError("Solution start times must cover each job exactly once")
        for job in domain.jobs:
            job.line = None
            job.start_time = None
            job.end_time = None
        for line in domain.lines:
            line.jobs = []
            for job_id in solution.line_routes[line.id]:
                job = jobs[job_id]
                start = solution.start_times[job_id]
                if not isinstance(start, datetime):
                    raise ValueError(f"Job {job_id} start time must be a datetime")
                job.line = line
                job.start_time = start
                job.end_time = start + job.duration
                line.jobs.append(job)
        metrics = domain.calculate_metrics()
        actual = (
            metrics["hard_penalty"],
            metrics["medium_penalty"],
            metrics["soft_penalty"],
        )
        expected = (
            solution.hard_penalty,
            solution.medium_penalty,
            solution.soft_penalty,
        )
        if actual != expected:
            raise ValueError("Reconstructed domain scores do not match solver result")
        if solution.mode == "strict" and not metrics["strict_feasible"]:
            raise ValueError("Strict solution violates business constraints")
        return domain
