"""Native heuristic pricing; every returned reduced cost is rechecked exactly."""

from functools import reduce
from math import ceil, gcd

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from ..cotwin import CotVRP
from .PricingSolver import PriceResult


class FastPricingSolver:
    @staticmethod
    def price(
        cotwin: CotVRP,
        group_index: int,
        customer_duals: dict[int, float],
        group_dual: float,
        components: tuple[float, float, float],
        seconds: float,
        *,
        max_columns: int = 8,
    ) -> tuple[PriceResult, ...]:
        if seconds <= 0 or not cotwin.customer_ids:
            return ()
        domain = cotwin.domain
        group = cotwin.groups[group_index]
        customer_ids = cotwin.customer_ids
        local_ids = (group.depot_id, *customer_ids)
        index_by_id = domain.index_by_id
        locations = domain.location_by_id
        matrix = domain.distance_matrix
        manager = pywrapcp.RoutingIndexManager(len(local_ids), 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        scale = 1000
        max_dual = max((abs(value) for value in customer_duals.values()), default=0)
        max_distance = max(map(max, matrix), default=0)
        raw_bound = len(customer_ids) * (
            abs(components[2]) * max_distance + 2 * max_dual + 1
        ) + abs(components[0]) * sum(locations[c].demand for c in customer_ids)
        while scale > 1 and raw_bound * scale >= (1 << 59):
            scale //= 10
        if raw_bound * scale >= (1 << 59):
            return ()
        scaled_duals = {c: round(customer_duals[c] * scale) for c in customer_ids}
        hard_weight, medium_weight, distance_weight = (
            round(value * scale) for value in components
        )
        shift = max(0, *scaled_duals.values())

        def arc_cost(source: int, target: int) -> int:
            if routing.IsStart(source) and routing.IsEnd(target):
                return 0
            left = local_ids[manager.IndexToNode(source)]
            right = local_ids[manager.IndexToNode(target)]
            cost = distance_weight * matrix[index_by_id[left]][index_by_id[right]]
            if not routing.IsEnd(target):
                cost += shift - scaled_duals[right]
            return cost

        arc_index = routing.RegisterTransitCallback(arc_cost)
        routing.SetArcCostEvaluatorOfAllVehicles(arc_index)
        for local_index in range(1, len(local_ids)):
            routing.AddDisjunction([manager.NodeToIndex(local_index)], shift)

        def demand(index: int) -> int:
            return locations[local_ids[manager.IndexToNode(index)]].demand

        demand_index = routing.RegisterUnaryTransitCallback(demand)
        if cotwin.mode == "strict":
            added = routing.AddDimensionWithVehicleCapacity(
                demand_index, 0, [group.capacity], True, "Load"
            )
        else:
            added = routing.AddDimension(
                demand_index,
                0,
                sum(locations[c].demand for c in customer_ids),
                True,
                "Load",
            )
        if not added:
            raise RuntimeError("Could not add pricing load dimension")
        if cotwin.mode == "penalized" and hard_weight > 0:
            load = routing.GetDimensionOrDie("Load")
            load.SetCumulVarSoftUpperBound(routing.End(0), group.capacity, hard_weight)

        if domain.time_windowed and (cotwin.mode == "strict" or medium_weight > 0):
            time_scale = reduce(
                gcd,
                (
                    value
                    for customer_id in local_ids
                    for value in (
                        locations[customer_id].time_window_start,
                        locations[customer_id].time_window_end,
                        locations[customer_id].service_time,
                    )
                ),
                0,
            )
            time_scale = (
                reduce(gcd, (group.work_day_start, group.work_day_end), time_scale) or 1
            )
            service = {
                customer: locations[customer].service_time // time_scale
                for customer in customer_ids
            }

            def service_time(index: int) -> int:
                return (
                    0
                    if routing.IsStart(index)
                    else service[local_ids[manager.IndexToNode(index)]]
                )

            service_index = routing.RegisterUnaryTransitCallback(service_time)
            time_bound = max(
                group.work_day_start // time_scale,
                *(locations[c].time_window_start // time_scale for c in customer_ids),
            ) + sum(service.values())
            time_capacity = (
                group.work_day_end // time_scale
                if cotwin.mode == "strict"
                else time_bound
            )
            if not routing.AddDimension(
                service_index, time_capacity, time_capacity, False, "Time"
            ):
                raise RuntimeError("Could not add pricing time dimension")
            time = routing.GetDimensionOrDie("Time")
            work_start = group.work_day_start // time_scale
            time.CumulVar(routing.Start(0)).SetRange(work_start, work_start)
            if cotwin.mode == "strict":
                time.CumulVar(routing.End(0)).SetMax(group.work_day_end // time_scale)
            elif medium_weight > 0:
                time.SetCumulVarSoftUpperBound(
                    routing.End(0),
                    group.work_day_end // time_scale,
                    round(components[1] * scale * time_scale),
                )
            routing.AddVariableMinimizedByFinalizer(time.CumulVar(routing.End(0)))
            for local_index, customer in enumerate(customer_ids, 1):
                clock = time.CumulVar(manager.NodeToIndex(local_index))
                location = locations[customer]
                window_start = location.time_window_start // time_scale
                latest_start = (
                    location.time_window_end - location.service_time
                ) // time_scale
                if cotwin.mode == "strict":
                    if window_start > min(latest_start, time_capacity):
                        routing.solver().Add(routing.solver().FalseConstraint())
                    else:
                        clock.SetRange(window_start, min(latest_start, time_capacity))
                else:
                    clock.SetMin(window_start)
                    time.SetCumulVarSoftUpperBound(
                        manager.NodeToIndex(local_index),
                        latest_start,
                        round(components[1] * scale * time_scale),
                    )
                routing.AddVariableMinimizedByFinalizer(clock)

        candidates: dict[tuple[int, ...], PriceResult] = {}

        def collect() -> None:
            index = routing.Start(0)
            route = []
            while not routing.IsEnd(index):
                index = routing.NextVar(index).Value()
                if not routing.IsEnd(index):
                    route.append(local_ids[manager.IndexToNode(index)])
            if not route or (group_index, tuple(route)) in cotwin.columns:
                return
            column = cotwin.make_column(group_index, tuple(route))
            reduced = (
                sum(a * b for a, b in zip(components, column.score))
                - sum(customer_duals[c] for c in route)
                - group_dual
            )
            if reduced < -1e-6:
                candidates[column.customers] = PriceResult(
                    column, reduced, False, "HEURISTIC"
                )

        routing.AddAtSolutionCallback(collect)
        routing.AddSearchMonitor(
            routing.solver().CustomLimit(lambda: len(candidates) >= max_columns)
        )
        parameters = pywrapcp.DefaultRoutingSearchParameters()
        parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        parameters.time_limit.FromMilliseconds(max(1, ceil(seconds * 1000)))
        routing.SolveWithParameters(parameters)
        return tuple(sorted(candidates.values(), key=lambda item: item.reduced_cost))
