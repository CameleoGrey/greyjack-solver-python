from dataclasses import dataclass
from functools import reduce
from math import gcd
from typing import Callable

from ortools.constraint_solver import pywrapcp

from ..cotwin import CotVRP
from ..domain import VehicleRoutingPlan


@dataclass(frozen=True)
class _RoutingFacts:
    location_ids: tuple[int, ...]
    customer_indices: frozenset[int]
    starts: list[int]
    matrix: tuple[tuple[int, ...], ...]
    demands: tuple[int, ...]
    vehicle_count: int
    hard_bound: int
    time_scale: int
    service_times: tuple[int, ...]
    time_bound: int
    medium_weight: int
    hard_weight: int
    objective_bound: int
    bounds: dict[str, int]


class CotwinBuilder:
    """Translate immutable business facts to an OR-Tools RoutingModel."""

    def __init__(self, *, mode: str = "penalized"):
        if mode not in ("penalized", "strict"):
            raise ValueError("mode must be 'penalized' or 'strict'")
        self.mode = mode

    def build_cotwin(self, domain: VehicleRoutingPlan) -> CotVRP:
        domain.validate()
        facts = self._checked_routing_facts(domain)
        manager = pywrapcp.RoutingIndexManager(
            len(facts.location_ids), facts.vehicle_count, facts.starts, facts.starts
        )
        routing = pywrapcp.RoutingModel(manager)
        callbacks = [
            self._add_distance_cost(routing, manager, facts),
            self._add_load_dimension(routing, manager, domain, facts),
        ]
        if domain.time_windowed:
            callbacks.append(self._add_time_dimension(routing, manager, domain, facts))

        return CotVRP(
            manager,
            routing,
            facts.location_ids,
            facts.customer_indices,
            facts.hard_weight,
            facts.medium_weight,
            facts.time_scale,
            facts.objective_bound,
            tuple(callbacks),
            self.mode,
        )

    def _checked_routing_facts(self, domain: VehicleRoutingPlan) -> _RoutingFacts:
        location_ids = tuple(location.id for location in domain.locations)
        id_to_index = domain.index_by_id
        customer_indices = frozenset(
            index
            for index, location in enumerate(domain.locations)
            if location.id not in domain.depot_ids
        )
        starts = [id_to_index[vehicle.depot_id] for vehicle in domain.vehicles]
        matrix = tuple(tuple(row) for row in domain.distance_matrix)
        demands = tuple(location.demand for location in domain.locations)
        customer_count = len(customer_indices)
        vehicle_count = len(domain.vehicles)
        max_distance = max((max(row) for row in matrix), default=0)
        distance_bound = (
            customer_count + min(customer_count, vehicle_count)
        ) * max_distance
        hard_bound = sum(demands[index] for index in customer_indices)

        if domain.time_windowed:
            # Exact unit reduction keeps the lexicographic objective within
            # int64 for datasets whose clocks use coarse units (for example,
            # the Belgium files use multiples of 300 seconds).
            time_scale = reduce(
                gcd,
                (
                    value
                    for index in customer_indices
                    for value in (
                        domain.locations[index].time_window_start,
                        domain.locations[index].time_window_end,
                        domain.locations[index].service_time,
                    )
                ),
                0,
            )
            time_scale = (
                reduce(
                    gcd,
                    (
                        value
                        for vehicle in domain.vehicles
                        for value in (vehicle.work_day_start, vehicle.work_day_end)
                    ),
                    time_scale,
                )
                or 1
            )
            service_times = tuple(
                location.service_time // time_scale for location in domain.locations
            )
            time_bound = max(
                [
                    *(
                        vehicle.work_day_start // time_scale
                        for vehicle in domain.vehicles
                    ),
                    *(
                        domain.locations[index].time_window_start // time_scale
                        for index in customer_indices
                    ),
                ]
            ) + sum(service_times[index] for index in customer_indices)
            medium_bound = sum(
                max(
                    0,
                    time_bound - domain.locations[index].time_window_end // time_scale,
                )
                for index in customer_indices
            ) + sum(
                max(0, time_bound - vehicle.work_day_end // time_scale)
                for vehicle in domain.vehicles
            )
        else:
            service_times = ()
            time_scale = 1
            time_bound = 0
            medium_bound = 0

        medium_weight = distance_bound + 1 if self.mode == "penalized" else 0
        hard_weight = (
            medium_bound * medium_weight + distance_bound + 1
            if self.mode == "penalized"
            else 0
        )
        objective_bound = (
            hard_bound * hard_weight + medium_bound * medium_weight + distance_bound
            if self.mode == "penalized"
            else distance_bound
        )
        safe_bound = ((1 << 63) - 1) // 4
        bounds = {
            "max_distance": max_distance,
            "distance_bound": distance_bound,
            "objective_bound": objective_bound,
        }
        if self.mode == "strict":
            bounds.update(
                {
                    "max_demand": max(demands, default=0),
                    "max_capacity": max(
                        vehicle.capacity for vehicle in domain.vehicles
                    ),
                    "time_capacity": (
                        max(
                            vehicle.work_day_end // time_scale
                            for vehicle in domain.vehicles
                        )
                        if domain.time_windowed
                        else 0
                    ),
                }
            )
        else:
            bounds.update(
                {
                    "hard_bound": hard_bound,
                    "time_bound": time_bound,
                    "medium_bound": medium_bound,
                    "medium_weight": medium_weight,
                    "hard_weight": hard_weight,
                }
            )
        for name, value in bounds.items():
            if value > safe_bound:
                raise ValueError(
                    "Dataset exceeds safe RoutingModel integer bounds: "
                    f"{name}={value} > {safe_bound}"
                )
        return _RoutingFacts(
            location_ids,
            customer_indices,
            starts,
            matrix,
            demands,
            vehicle_count,
            hard_bound,
            time_scale,
            service_times,
            time_bound,
            medium_weight,
            hard_weight,
            objective_bound,
            bounds,
        )

    @staticmethod
    def _add_distance_cost(
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        facts: _RoutingFacts,
    ) -> Callable[[int, int], int]:
        def distance_callback(source: int, target: int) -> int:
            # An unused vehicle contributes no depot-to-depot business distance.
            if routing.IsStart(source) and routing.IsEnd(target):
                return 0
            return facts.matrix[manager.IndexToNode(source)][
                manager.IndexToNode(target)
            ]

        distance_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(distance_index)
        return distance_callback

    def _add_load_dimension(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        domain: VehicleRoutingPlan,
        facts: _RoutingFacts,
    ) -> Callable[[int], int]:
        def demand_callback(index: int) -> int:
            return facts.demands[manager.IndexToNode(index)]

        demand_index = routing.RegisterUnaryTransitCallback(demand_callback)
        if self.mode == "strict":
            load_added = routing.AddDimensionWithVehicleCapacity(
                demand_index,
                0,
                [vehicle.capacity for vehicle in domain.vehicles],
                True,
                "Load",
            )
        else:
            load_added = routing.AddDimension(
                demand_index, 0, facts.hard_bound, True, "Load"
            )
        if not load_added:
            raise RuntimeError("Could not add the Load dimension")
        load = routing.GetDimensionOrDie("Load")
        if self.mode == "penalized":
            for vehicle_index, vehicle in enumerate(domain.vehicles):
                load.SetCumulVarSoftUpperBound(
                    routing.End(vehicle_index), vehicle.capacity, facts.hard_weight
                )
        return demand_callback

    def _add_time_dimension(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        domain: VehicleRoutingPlan,
        facts: _RoutingFacts,
    ) -> Callable[[int], int]:
        def service_callback(index: int) -> int:
            if routing.IsStart(index):
                return 0
            return facts.service_times[manager.IndexToNode(index)]

        service_index = routing.RegisterUnaryTransitCallback(service_callback)
        time_capacity = (
            facts.bounds["time_capacity"] if self.mode == "strict" else facts.time_bound
        )
        if not routing.AddDimension(
            service_index, time_capacity, time_capacity, False, "Time"
        ):
            raise RuntimeError("Could not add the Time dimension")
        time = routing.GetDimensionOrDie("Time")
        for vehicle_index, vehicle in enumerate(domain.vehicles):
            start = time.CumulVar(routing.Start(vehicle_index))
            work_day_start = vehicle.work_day_start // facts.time_scale
            start.SetRange(work_day_start, work_day_start)
            end = time.CumulVar(routing.End(vehicle_index))
            if self.mode == "strict":
                end.SetMax(vehicle.work_day_end // facts.time_scale)
            else:
                time.SetCumulVarSoftUpperBound(
                    routing.End(vehicle_index),
                    vehicle.work_day_end // facts.time_scale,
                    facts.medium_weight,
                )
            routing.AddVariableMinimizedByFinalizer(end)
        for customer_index in facts.customer_indices:
            customer = domain.locations[customer_index]
            routing_index = manager.NodeToIndex(customer_index)
            clock = time.CumulVar(routing_index)
            window_start = customer.time_window_start // facts.time_scale
            latest_start = (
                customer.time_window_end - customer.service_time
            ) // facts.time_scale
            if self.mode == "strict":
                if window_start > min(latest_start, time_capacity):
                    routing.solver().Add(routing.solver().FalseConstraint())
                else:
                    clock.SetRange(window_start, min(latest_start, time_capacity))
            else:
                clock.SetMin(window_start)
                # Cumul is service start; the business penalty uses completion.
                time.SetCumulVarSoftUpperBound(
                    routing_index, latest_start, facts.medium_weight
                )
            routing.AddVariableMinimizedByFinalizer(clock)
        return service_callback
