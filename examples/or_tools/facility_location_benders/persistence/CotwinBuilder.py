"""Build the opening master and exact integer score bounds."""

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
        hard_weight, assignment_upper = self._checked_bounds(snapshot, distances)
        master = cp_model.CpModel()
        openings = self._add_openings(master, snapshot)
        assignment_cost = self._add_objective(
            master, snapshot, openings, assignment_upper
        )
        validation_error = master.validate()
        if validation_error:
            raise ValueError(f"Invalid Benders master: {validation_error}")
        return CotFacilityLocation(
            snapshot,
            master,
            openings,
            assignment_cost,
            distances,
            hard_weight,
            assignment_upper,
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
    ) -> tuple[int, int]:
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
        return hard_weight, assignment_upper

    def _add_openings(
        self, model: cp_model.CpModel, domain: FacilityLocationDomain
    ) -> dict[int, cp_model.IntVar]:
        openings = {
            facility.id: model.new_bool_var(f"open_{facility.id}")
            for facility in domain.facilities
        }
        if not domain.consumers:
            for variable in openings.values():
                model.add(variable == 0)
            return openings

        model.add(sum(openings.values()) >= 1)
        model.add(sum(openings.values()) <= len(domain.consumers))
        if self.mode == "strict":
            model.add(
                sum(f.capacity * openings[f.id] for f in domain.facilities)
                >= sum(c.demand for c in domain.consumers)
            )
            for consumer in domain.consumers:
                eligible = [
                    openings[f.id]
                    for f in domain.facilities
                    if f.capacity >= consumer.demand
                ]
                model.add(sum(eligible) >= 1)
        return openings

    @staticmethod
    def _add_objective(
        model: cp_model.CpModel,
        domain: FacilityLocationDomain,
        openings: dict[int, cp_model.IntVar],
        assignment_upper: int,
    ) -> cp_model.IntVar:
        assignment_cost = model.new_int_var(0, assignment_upper, "assignment_cost")
        model.minimize(
            assignment_cost
            + sum(2 * f.setup_cost * openings[f.id] for f in domain.facilities)
        )
        return assignment_cost
