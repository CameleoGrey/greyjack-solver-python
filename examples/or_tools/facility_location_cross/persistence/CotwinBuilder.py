"""Build a validated business cotwin for the Cross models."""

from copy import deepcopy

from ortools.sat.python import cp_model

from ..cotwin import CotFacilityLocation
from ..domain import FacilityLocationDomain


class CotwinBuilder:
    def __init__(self, *, mode: str = "strict", use_greedy_seed: bool = True):
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode
        self.use_greedy_seed = use_greedy_seed

    def build_cotwin(self, domain: FacilityLocationDomain) -> CotFacilityLocation:
        domain.validate()
        snapshot = deepcopy(domain)
        distances = self._distances(snapshot)
        hard_weight, assignment_upper, setup_lower, setup_upper = self._checked_bounds(
            snapshot, distances
        )
        return CotFacilityLocation(
            snapshot,
            distances,
            hard_weight,
            assignment_upper,
            setup_lower,
            setup_upper,
            self.mode,
            self.use_greedy_seed,
        )

    @staticmethod
    def _distances(domain: FacilityLocationDomain) -> dict[tuple[int, int], int]:
        return {
            (consumer.id, facility.id): consumer.location.get_distance_to(
                facility.location
            )
            for consumer in domain.consumers
            for facility in domain.facilities
        }

    def _checked_bounds(
        self,
        domain: FacilityLocationDomain,
        distances: dict[tuple[int, int], int],
    ) -> tuple[int, int, int, int]:
        total_demand = sum(consumer.demand for consumer in domain.consumers)
        setup_lower = 2 * sum(min(0, f.setup_cost) for f in domain.facilities)
        setup_upper = 2 * sum(max(0, f.setup_cost) for f in domain.facilities)
        distance_upper = 5 * sum(
            max(distances[consumer.id, facility.id] for facility in domain.facilities)
            for consumer in domain.consumers
        )
        soft_upper = setup_upper + distance_upper
        hard_weight = soft_upper - setup_lower + 1 if self.mode == "penalized" else 0
        assignment_upper = distance_upper + hard_weight * total_demand
        safe_bound = cp_model.INT_MAX // 2
        values = (
            total_demand,
            abs(setup_lower),
            abs(setup_upper),
            soft_upper,
            hard_weight,
            assignment_upper,
            assignment_upper + setup_upper,
            *(f.capacity for f in domain.facilities),
            *(abs(2 * f.setup_cost) for f in domain.facilities),
            *(5 * distance for distance in distances.values()),
        )
        if any(value > safe_bound for value in values):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")
        return hard_weight, assignment_upper, setup_lower, setup_upper
