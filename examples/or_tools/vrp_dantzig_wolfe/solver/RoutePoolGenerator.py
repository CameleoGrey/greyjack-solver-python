"""Collect compatible route columns from native OR-Tools complete VRP searches."""

from dataclasses import dataclass
from functools import reduce
from math import ceil, gcd
from time import monotonic
from typing import Callable

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from ..cotwin import CotVRP


@dataclass(frozen=True)
class PoolResult:
    best_routes: tuple[tuple[int, ...], ...] | None
    best_score: tuple[int, int, int] | None
    solutions: int
    elapsed_seconds: float


class RoutePoolGenerator:
    STRATEGIES = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC,
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION,
    )

    @staticmethod
    def generate(
        cotwin: CotVRP,
        seconds: float,
        strategy: int,
        *,
        max_columns: int = 10_000,
        on_solution: Callable[[tuple[int, int, int]], None] | None = None,
    ) -> PoolResult:
        started = monotonic()
        domain = cotwin.domain
        n = len(domain.locations)
        customer_count = len(cotwin.customer_ids)
        if customer_count == 0 or seconds <= 0:
            return PoolResult(None, None, 0, monotonic() - started)
        ids = tuple(location.id for location in domain.locations)
        indices = domain.index_by_id
        starts = [indices[vehicle.depot_id] for vehicle in domain.vehicles]
        manager = pywrapcp.RoutingIndexManager(n, len(domain.vehicles), starts, starts)
        routing = pywrapcp.RoutingModel(manager)
        matrix = domain.distance_matrix
        demands = tuple(location.demand for location in domain.locations)
        max_distance = max(map(max, matrix), default=0)
        distance_bound = (
            customer_count + min(customer_count, len(domain.vehicles))
        ) * max_distance

        def distance_callback(source: int, target: int) -> int:
            if routing.IsStart(source) and routing.IsEnd(target):
                return 0
            return matrix[manager.IndexToNode(source)][manager.IndexToNode(target)]

        distance_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(distance_index)

        if domain.time_windowed:
            time_scale = reduce(
                gcd,
                (
                    value
                    for location in domain.locations
                    for value in (
                        location.time_window_start,
                        location.time_window_end,
                        location.service_time,
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
            service = tuple(
                location.service_time // time_scale for location in domain.locations
            )
            time_bound = max(
                [
                    *(
                        vehicle.work_day_start // time_scale
                        for vehicle in domain.vehicles
                    ),
                    *(
                        domain.location_by_id[c].time_window_start // time_scale
                        for c in cotwin.customer_ids
                    ),
                ]
            ) + sum(
                domain.location_by_id[c].service_time // time_scale
                for c in cotwin.customer_ids
            )
            medium_bound = sum(
                max(
                    0,
                    time_bound - domain.location_by_id[c].time_window_end // time_scale,
                )
                for c in cotwin.customer_ids
            ) + sum(
                max(0, time_bound - vehicle.work_day_end // time_scale)
                for vehicle in domain.vehicles
            )
        else:
            time_scale = 1
            service = ()
            time_bound = 0
            medium_bound = 0
        medium_weight = distance_bound + 1
        hard_weight = medium_bound * medium_weight + distance_bound + 1
        total_demand = sum(domain.location_by_id[c].demand for c in cotwin.customer_ids)
        if cotwin.mode == "penalized" and (
            total_demand * hard_weight + medium_bound * medium_weight + distance_bound
            >= (1 << 61)
        ):
            raise ValueError("Dataset exceeds safe RoutingModel objective bounds")

        def demand_callback(index: int) -> int:
            return demands[manager.IndexToNode(index)]

        demand_index = routing.RegisterUnaryTransitCallback(demand_callback)
        if cotwin.mode == "strict":
            added = routing.AddDimensionWithVehicleCapacity(
                demand_index,
                0,
                [vehicle.capacity for vehicle in domain.vehicles],
                True,
                "Load",
            )
        else:
            added = routing.AddDimension(demand_index, 0, total_demand, True, "Load")
        if not added:
            raise RuntimeError("Could not add route-pool load dimension")
        load = routing.GetDimensionOrDie("Load")
        if cotwin.mode == "penalized":
            for vehicle_index, vehicle in enumerate(domain.vehicles):
                load.SetCumulVarSoftUpperBound(
                    routing.End(vehicle_index), vehicle.capacity, hard_weight
                )

        if domain.time_windowed:

            def service_callback(index: int) -> int:
                return (
                    0 if routing.IsStart(index) else service[manager.IndexToNode(index)]
                )

            service_index = routing.RegisterUnaryTransitCallback(service_callback)
            time_capacity = (
                max(vehicle.work_day_end // time_scale for vehicle in domain.vehicles)
                if cotwin.mode == "strict"
                else time_bound
            )
            if not routing.AddDimension(
                service_index, time_capacity, time_capacity, False, "Time"
            ):
                raise RuntimeError("Could not add route-pool time dimension")
            time = routing.GetDimensionOrDie("Time")
            for vehicle_index, vehicle in enumerate(domain.vehicles):
                start = time.CumulVar(routing.Start(vehicle_index))
                work_start = vehicle.work_day_start // time_scale
                start.SetRange(work_start, work_start)
                end = time.CumulVar(routing.End(vehicle_index))
                if cotwin.mode == "strict":
                    end.SetMax(vehicle.work_day_end // time_scale)
                else:
                    time.SetCumulVarSoftUpperBound(
                        routing.End(vehicle_index),
                        vehicle.work_day_end // time_scale,
                        medium_weight,
                    )
                routing.AddVariableMinimizedByFinalizer(end)
            for customer_id in cotwin.customer_ids:
                customer_index = indices[customer_id]
                customer = domain.locations[customer_index]
                routing_index = manager.NodeToIndex(customer_index)
                clock = time.CumulVar(routing_index)
                window_start = customer.time_window_start // time_scale
                latest_start = (
                    customer.time_window_end - customer.service_time
                ) // time_scale
                if cotwin.mode == "strict":
                    if window_start > min(latest_start, time_capacity):
                        routing.solver().Add(routing.solver().FalseConstraint())
                    else:
                        clock.SetRange(window_start, min(latest_start, time_capacity))
                else:
                    clock.SetMin(window_start)
                    time.SetCumulVarSoftUpperBound(
                        routing_index, latest_start, medium_weight
                    )
                routing.AddVariableMinimizedByFinalizer(clock)

        groups_by_vehicle = {
            vehicle: group_index
            for group_index, group in enumerate(cotwin.groups)
            for vehicle in group.vehicle_indices
        }
        best_routes = None
        best_score = None
        seen_assignments: set[tuple[tuple[int, ...], ...]] = set()

        def collect() -> None:
            nonlocal best_routes, best_score
            routes = []
            for vehicle_index in range(len(domain.vehicles)):
                route = []
                index = routing.Start(vehicle_index)
                while not routing.IsEnd(index):
                    index = routing.NextVar(index).Value()
                    if not routing.IsEnd(index):
                        route.append(ids[manager.IndexToNode(index)])
                routes.append(tuple(route))
            assignment = tuple(routes)
            if assignment in seen_assignments:
                return
            seen_assignments.add(assignment)
            covered = [customer for route in assignment for customer in route]
            if len(covered) != customer_count or set(covered) != set(
                cotwin.customer_ids
            ):
                raise RuntimeError(
                    "Route-pool assignment does not cover every customer"
                )
            columns = [
                cotwin.make_column(groups_by_vehicle[i], route)
                for i, route in enumerate(assignment)
                if route
            ]
            score = tuple(sum(column.score[j] for column in columns) for j in range(3))
            if on_solution is not None:
                on_solution(score)
            improved = best_score is None or score < best_score
            if improved:
                best_routes, best_score = assignment, score
            if len(cotwin.columns) < max_columns or improved:
                for column in columns:
                    cotwin.add_column(column.group, column.customers)

        routing.AddAtSolutionCallback(collect)
        remaining = seconds - (monotonic() - started)
        if remaining > 0:
            parameters = pywrapcp.DefaultRoutingSearchParameters()
            parameters.first_solution_strategy = strategy
            parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            parameters.time_limit.FromMilliseconds(max(1, ceil(remaining * 1000)))
            routing.SolveWithParameters(parameters)
        return PoolResult(
            best_routes, best_score, len(seen_assignments), monotonic() - started
        )
