from collections import defaultdict
from copy import deepcopy

from ..cotwin.CotVRP import CotVRP, VehicleGroup
from ..domain import VehicleRoutingPlan


class CotwinBuilder:
    def __init__(self, *, mode: str = "penalized"):
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode

    def build_cotwin(self, domain: VehicleRoutingPlan) -> CotVRP:
        domain.validate()
        snapshot = deepcopy(domain)
        # Input routes are an incumbent, not part of the problem definition.
        for vehicle in snapshot.vehicles:
            vehicle.customer_list = []
        buckets: dict[tuple[int, int, int | None, int | None], list[int]] = defaultdict(
            list
        )
        for index, vehicle in enumerate(snapshot.vehicles):
            key = (
                vehicle.depot_id,
                vehicle.capacity,
                vehicle.work_day_start,
                vehicle.work_day_end,
            )
            buckets[key].append(index)
        groups = tuple(
            VehicleGroup(*key, tuple(indices)) for key, indices in buckets.items()
        )
        customers = tuple(
            location.id
            for location in snapshot.locations
            if location.id not in snapshot.depot_ids
        )
        self._check_numeric_bounds(snapshot, customers)
        return CotVRP(snapshot, self.mode, customers, groups)

    @staticmethod
    def _check_numeric_bounds(
        domain: VehicleRoutingPlan, customers: tuple[int, ...]
    ) -> None:
        # GLOP and SCIP use floating-point coefficients. Keep all raw route
        # components and timing big-M values well below exact-double limits.
        limit = 1 << 40
        maximum_distance = max((max(row) for row in domain.distance_matrix), default=0)
        distance_bound = (
            len(customers) + min(len(customers), len(domain.vehicles))
        ) * maximum_distance
        demand_bound = sum(domain.location_by_id[c].demand for c in customers)
        bounds = [distance_bound, demand_bound]
        if domain.time_windowed:
            time_bound = max(
                [
                    *(vehicle.work_day_start for vehicle in domain.vehicles),
                    *(domain.location_by_id[c].time_window_start for c in customers),
                ]
            ) + sum(domain.location_by_id[c].service_time for c in customers)
            bounds.append(time_bound)
            medium_bound = sum(
                max(0, time_bound - domain.location_by_id[c].time_window_end)
                for c in customers
            ) + sum(
                max(0, time_bound - vehicle.work_day_end) for vehicle in domain.vehicles
            )
            bounds.append(medium_bound)
            bounds.append(
                2 * time_bound
                + max(
                    (domain.location_by_id[c].service_time for c in customers),
                    default=0,
                )
                + max(
                    (domain.location_by_id[c].time_window_end for c in customers),
                    default=0,
                )
                + 1
            )
        if any(bound >= limit for bound in bounds):
            raise ValueError("Dataset exceeds safe decomposition numeric bounds")
