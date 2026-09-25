"""Build and independently reconstruct business facility assignments."""

from copy import deepcopy

from ..domain import FacilityLocationDomain
from ..solver.FacilityLocationSolution import FacilityLocationSolution
from .DemoDataBuilder import DemoDataBuilder
from .DemoDataGenerator import DemoDataGenerator


class DomainBuilder:
    def __init__(self, seed: int = 0, demo_data_builder: DemoDataBuilder | None = None):
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        self.seed = seed
        self.demo_data_builder = demo_data_builder

    def build_domain_from_scratch(self) -> FacilityLocationDomain:
        if self.demo_data_builder is None:
            return DemoDataGenerator(self.seed).generate_demo_data()
        return self.demo_data_builder.build(self.seed)

    def build_from_domain(
        self, domain: FacilityLocationDomain
    ) -> FacilityLocationDomain:
        domain.validate()
        return deepcopy(domain)

    def build_from_solution(
        self,
        solution: FacilityLocationSolution,
        initial_domain: FacilityLocationDomain | None = None,
    ) -> FacilityLocationDomain:
        if not solution.has_solution:
            raise ValueError(
                f"Cannot reconstruct a solution with status {solution.status}"
            )
        domain = (
            self.build_domain_from_scratch()
            if initial_domain is None
            else self.build_from_domain(initial_domain)
        )
        consumer_ids = {consumer.id for consumer in domain.consumers}
        if set(solution.assignments) != consumer_ids:
            raise ValueError("Solution must assign exactly the domain's consumer IDs")
        facilities = {facility.id: facility for facility in domain.facilities}
        if any(fid not in facilities for fid in solution.assignments.values()):
            raise ValueError("Solution references unknown facility")
        for consumer in domain.consumers:
            consumer.facility = facilities[solution.assignments[consumer.id]]
        metrics = domain.calculate_metrics()
        if (metrics["hard_penalty"], metrics["soft_cost"]) != (
            solution.hard_penalty,
            solution.soft_cost,
        ):
            raise ValueError("Reconstructed domain scores do not match solver result")
        if solution.mode == "strict" and metrics["hard_penalty"]:
            raise ValueError("Strict solution violates facility capacity")
        return domain
