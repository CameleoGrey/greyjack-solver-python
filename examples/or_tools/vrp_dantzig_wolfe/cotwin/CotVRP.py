from dataclasses import dataclass, field

from ..domain import VehicleRoutingPlan


@dataclass(frozen=True)
class VehicleGroup:
    depot_id: int
    capacity: int
    work_day_start: int | None
    work_day_end: int | None
    vehicle_indices: tuple[int, ...]


@dataclass(frozen=True)
class RouteColumn:
    group: int
    customers: tuple[int, ...]
    hard_penalty: int
    medium_penalty: int
    distance: int

    @property
    def score(self) -> tuple[int, int, int]:
        return self.hard_penalty, self.medium_penalty, self.distance


@dataclass
class CotVRP:
    domain: VehicleRoutingPlan
    mode: str
    customer_ids: tuple[int, ...]
    groups: tuple[VehicleGroup, ...]
    columns: dict[tuple[int, tuple[int, ...]], RouteColumn] = field(
        default_factory=dict
    )

    def make_column(self, group_index: int, route: tuple[int, ...]) -> RouteColumn:
        if not route or len(route) != len(set(route)):
            raise ValueError("A route must contain distinct customers")
        if group_index not in range(len(self.groups)):
            raise ValueError("Unknown vehicle group")
        if any(customer not in self.customer_ids for customer in route):
            raise ValueError("A route contains an unknown customer")
        group = self.groups[group_index]
        locations = self.domain.location_by_id
        indices = self.domain.index_by_id
        matrix = self.domain.distance_matrix
        current = group.depot_id
        load = 0
        distance = 0
        medium = 0
        clock = group.work_day_start
        for customer_id in route:
            customer = locations[customer_id]
            distance += matrix[indices[current]][indices[customer_id]]
            load += customer.demand
            if self.domain.time_windowed:
                clock = max(clock, customer.time_window_start) + customer.service_time
                medium += max(0, clock - customer.time_window_end)
            current = customer_id
        distance += matrix[indices[current]][indices[group.depot_id]]
        hard = max(0, load - group.capacity)
        if self.domain.time_windowed:
            medium += max(0, clock - group.work_day_end)
        if self.mode == "strict" and (hard or medium):
            raise ValueError("Route violates strict capacity or time bounds")
        return RouteColumn(group_index, route, hard, medium, distance)

    def add_column(self, group_index: int, route: tuple[int, ...]) -> bool:
        key = group_index, route
        if key in self.columns:
            return False
        self.columns[key] = self.make_column(group_index, route)
        return True
