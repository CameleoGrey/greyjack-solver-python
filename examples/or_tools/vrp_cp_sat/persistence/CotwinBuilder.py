from ortools.sat.python import cp_model

from ..cotwin import CotVRP
from ..domain import VehicleRoutingPlan


class CotwinBuilder:
    def __init__(self, use_greedy_hints: bool = True, *, mode: str = "penalized"):
        if mode not in ("penalized", "strict"):
            raise ValueError("mode must be 'penalized' or 'strict'")
        self.use_greedy_hints = use_greedy_hints
        self.mode = mode

    def build_cotwin(self, domain: VehicleRoutingPlan) -> CotVRP:
        domain.validate()
        location_ids = tuple(location.id for location in domain.locations)
        location_indices = domain.index_by_id
        customers = tuple(
            index
            for index, location in enumerate(domain.locations)
            if location.id not in domain.depot_ids
        )
        depots = tuple(
            location_indices[vehicle.depot_id] for vehicle in domain.vehicles
        )
        customer_count = len(customers)
        vehicle_count = len(domain.vehicles)
        max_distance = max((max(row) for row in domain.distance_matrix), default=0)
        distance_bound = (
            customer_count + min(customer_count, vehicle_count)
        ) * max_distance
        hard_bound = sum(domain.locations[index].demand for index in customers)
        if domain.time_windowed:
            latest_start = max(
                [
                    *(vehicle.work_day_start for vehicle in domain.vehicles),
                    *(domain.locations[index].time_window_start for index in customers),
                ]
            )
            time_bound = latest_start + sum(
                domain.locations[index].service_time for index in customers
            )
            medium_bound = sum(
                max(0, time_bound - domain.locations[index].time_window_end)
                for index in customers
            ) + sum(
                max(0, time_bound - vehicle.work_day_end) for vehicle in domain.vehicles
            )
        else:
            time_bound = 0
            medium_bound = 0
        medium_weight = distance_bound + 1 if self.mode == "penalized" else 0
        hard_weight = (
            medium_bound * medium_weight + distance_bound + 1
            if self.mode == "penalized"
            else 0
        )
        safe_bound = cp_model.INT_MAX // 2
        bounds = [max_distance, distance_bound, hard_bound, time_bound, medium_bound]
        if self.mode == "penalized":
            bounds.extend(
                (
                    medium_weight,
                    hard_weight,
                    hard_bound * hard_weight
                    + medium_bound * medium_weight
                    + distance_bound,
                )
            )
        if any(value > safe_bound for value in bounds):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")

        model = cp_model.CpModel()
        arcs: dict[tuple[int, int, int], cp_model.IntVar] = {}
        assigned: dict[tuple[int, int], cp_model.IntVar] = {}
        used: dict[int, cp_model.IntVar] = {}
        order = {
            index: model.new_int_var(1, customer_count, f"order_{index}")
            for index in customers
        }
        for vehicle_index, depot in enumerate(depots):
            used[vehicle_index] = model.new_bool_var(f"used_{vehicle_index}")
            for customer in customers:
                assigned[vehicle_index, customer] = model.new_bool_var(
                    f"assigned_{vehicle_index}_{customer}"
                )
                arcs[vehicle_index, depot, customer] = model.new_bool_var(
                    f"arc_{vehicle_index}_{depot}_{customer}"
                )
                arcs[vehicle_index, customer, depot] = model.new_bool_var(
                    f"arc_{vehicle_index}_{customer}_{depot}"
                )
                for other in customers:
                    if other != customer:
                        arcs[vehicle_index, customer, other] = model.new_bool_var(
                            f"arc_{vehicle_index}_{customer}_{other}"
                        )
        for customer in customers:
            model.add_exactly_one(assigned[v, customer] for v in range(vehicle_count))
        for vehicle_index, depot in enumerate(depots):
            model.add(
                sum(arcs[vehicle_index, depot, i] for i in customers)
                == used[vehicle_index]
            )
            model.add(
                sum(arcs[vehicle_index, i, depot] for i in customers)
                == used[vehicle_index]
            )
            for customer in customers:
                model.add(
                    arcs[vehicle_index, depot, customer]
                    + sum(
                        arcs[vehicle_index, other, customer]
                        for other in customers
                        if other != customer
                    )
                    == assigned[vehicle_index, customer]
                )
                model.add(
                    arcs[vehicle_index, customer, depot]
                    + sum(
                        arcs[vehicle_index, customer, other]
                        for other in customers
                        if other != customer
                    )
                    == assigned[vehicle_index, customer]
                )
                for other in customers:
                    if other != customer:
                        # MTZ: order strictly rises on every chosen customer arc.
                        model.add(order[other] >= order[customer] + 1).only_enforce_if(
                            arcs[vehicle_index, customer, other]
                        )

        overloads = {}
        for vehicle_index, vehicle in enumerate(domain.vehicles):
            load = sum(
                domain.locations[customer].demand * assigned[vehicle_index, customer]
                for customer in customers
            )
            overload = model.new_int_var(0, hard_bound, f"overload_{vehicle_index}")
            model.add_max_equality(overload, [0, load - vehicle.capacity])
            overloads[vehicle_index] = overload

        arrival: dict[int, cp_model.IntVar] = {}
        service_start: dict[int, cp_model.IntVar] = {}
        customer_lateness: dict[int, cp_model.IntVar] = {}
        return_time: dict[int, cp_model.IntVar] = {}
        vehicle_lateness: dict[int, cp_model.IntVar] = {}
        if domain.time_windowed:
            for customer in customers:
                location = domain.locations[customer]
                arrival[customer] = model.new_int_var(
                    0, time_bound, f"arrival_{customer}"
                )
                service_start[customer] = model.new_int_var(
                    0, time_bound, f"service_start_{customer}"
                )
                model.add_max_equality(
                    service_start[customer],
                    [arrival[customer], location.time_window_start],
                )
                customer_lateness[customer] = model.new_int_var(
                    0,
                    max(0, time_bound - location.time_window_end),
                    f"lateness_{customer}",
                )
                model.add_max_equality(
                    customer_lateness[customer],
                    [
                        0,
                        service_start[customer]
                        + location.service_time
                        - location.time_window_end,
                    ],
                )
            for vehicle_index, vehicle in enumerate(domain.vehicles):
                depot = depots[vehicle_index]
                return_time[vehicle_index] = model.new_int_var(
                    0, time_bound, f"return_{vehicle_index}"
                )
                model.add(
                    return_time[vehicle_index] == vehicle.work_day_start
                ).only_enforce_if(used[vehicle_index].Not())
                vehicle_lateness[vehicle_index] = model.new_int_var(
                    0,
                    max(0, time_bound - vehicle.work_day_end),
                    f"workday_lateness_{vehicle_index}",
                )
                model.add_max_equality(
                    vehicle_lateness[vehicle_index],
                    [0, return_time[vehicle_index] - vehicle.work_day_end],
                )
                for customer in customers:
                    model.add(
                        arrival[customer] == vehicle.work_day_start
                    ).only_enforce_if(arcs[vehicle_index, depot, customer])
                    model.add(
                        return_time[vehicle_index]
                        == service_start[customer]
                        + domain.locations[customer].service_time
                    ).only_enforce_if(arcs[vehicle_index, customer, depot])
                    for other in customers:
                        if other != customer:
                            model.add(
                                arrival[other]
                                == service_start[customer]
                                + domain.locations[customer].service_time
                            ).only_enforce_if(arcs[vehicle_index, customer, other])

        hard_penalty = model.new_int_var(0, hard_bound, "hard_penalty")
        medium_penalty = model.new_int_var(0, medium_bound, "medium_penalty")
        distance = model.new_int_var(0, distance_bound, "distance")
        model.add(hard_penalty == sum(overloads.values()))
        model.add(
            medium_penalty
            == sum(customer_lateness.values()) + sum(vehicle_lateness.values())
        )
        model.add(
            distance
            == sum(
                domain.distance_matrix[source][target] * variable
                for (_, source, target), variable in arcs.items()
            )
        )
        if self.mode == "strict":
            for penalty in (
                *overloads.values(),
                *customer_lateness.values(),
                *vehicle_lateness.values(),
            ):
                model.add(penalty == 0)
            model.add(hard_penalty == 0)
            model.add(medium_penalty == 0)
            model.minimize(distance)
        else:
            model.minimize(
                hard_weight * hard_penalty + medium_weight * medium_penalty + distance
            )
        cotwin = CotVRP(
            model,
            arcs,
            assigned,
            used,
            order,
            overloads,
            arrival,
            service_start,
            customer_lateness,
            return_time,
            vehicle_lateness,
            hard_penalty,
            medium_penalty,
            distance,
            location_ids,
            customers,
            depots,
            medium_weight,
            hard_weight,
            self.mode,
        )
        if self.use_greedy_hints:
            self._add_greedy_hints(domain, cotwin)
        validation_error = model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        return cotwin

    @staticmethod
    def _add_greedy_hints(domain: VehicleRoutingPlan, cotwin: CotVRP) -> None:
        """Supply an entire feasible (possibly overloaded) route assignment."""
        model = cotwin.model
        customers = cotwin.customer_indices
        routes: list[list[int]] = [[] for _ in domain.vehicles]
        loads = [0 for _ in domain.vehicles]
        remaining = set(customers)
        for vehicle_index, vehicle in enumerate(domain.vehicles):
            current = cotwin.vehicle_depots[vehicle_index]
            while True:
                feasible = [
                    customer
                    for customer in remaining
                    if loads[vehicle_index] + domain.locations[customer].demand
                    <= vehicle.capacity
                ]
                if not feasible:
                    break
                next_customer = min(
                    feasible,
                    key=lambda customer: (
                        domain.distance_matrix[current][customer],
                        customer,
                    ),
                )
                routes[vehicle_index].append(next_customer)
                remaining.remove(next_customer)
                loads[vehicle_index] += domain.locations[next_customer].demand
                current = next_customer
        for customer in sorted(remaining):
            vehicle_index = min(
                range(len(domain.vehicles)),
                key=lambda index: (
                    max(
                        0,
                        loads[index]
                        + domain.locations[customer].demand
                        - domain.vehicles[index].capacity,
                    )
                    - max(0, loads[index] - domain.vehicles[index].capacity),
                    domain.distance_matrix[
                        routes[index][-1]
                        if routes[index]
                        else cotwin.vehicle_depots[index]
                    ][customer],
                    index,
                ),
            )
            routes[vehicle_index].append(customer)
            loads[vehicle_index] += domain.locations[customer].demand

        selected_arcs = set()
        selected_assignments = set()
        orders = {}
        arrivals = {}
        starts = {}
        customer_lateness = {}
        returns = {}
        vehicle_lateness = {}
        for vehicle_index, route in enumerate(routes):
            depot = cotwin.vehicle_depots[vehicle_index]
            if route:
                selected_arcs.add((vehicle_index, depot, route[0]))
                selected_arcs.add((vehicle_index, route[-1], depot))
                selected_arcs.update(
                    (vehicle_index, left, right)
                    for left, right in zip(route, route[1:])
                )
            selected_assignments.update((vehicle_index, customer) for customer in route)
            for position, customer in enumerate(route, 1):
                orders[customer] = position
            if domain.time_windowed:
                clock = domain.vehicles[vehicle_index].work_day_start
                for customer in route:
                    location = domain.locations[customer]
                    arrivals[customer] = clock
                    starts[customer] = max(clock, location.time_window_start)
                    clock = starts[customer] + location.service_time
                    customer_lateness[customer] = max(
                        0, clock - location.time_window_end
                    )
                returns[vehicle_index] = clock
                vehicle_lateness[vehicle_index] = (
                    max(0, clock - domain.vehicles[vehicle_index].work_day_end)
                    if route
                    else 0
                )
        overloads = {
            vehicle_index: max(0, load - domain.vehicles[vehicle_index].capacity)
            for vehicle_index, load in enumerate(loads)
        }
        distance = sum(
            domain.distance_matrix[source][target]
            for _, source, target in selected_arcs
        )
        for key, variable in cotwin.arcs.items():
            model.add_hint(variable, int(key in selected_arcs))
        for key, variable in cotwin.assigned.items():
            model.add_hint(variable, int(key in selected_assignments))
        for vehicle_index, variable in cotwin.used.items():
            model.add_hint(variable, int(bool(routes[vehicle_index])))
        for customer, variable in cotwin.order.items():
            model.add_hint(variable, orders[customer])
        for vehicle_index, variable in cotwin.overloads.items():
            model.add_hint(variable, overloads[vehicle_index])
        for customer, variable in cotwin.arrival.items():
            model.add_hint(variable, arrivals[customer])
        for customer, variable in cotwin.service_start.items():
            model.add_hint(variable, starts[customer])
        for customer, variable in cotwin.customer_lateness.items():
            model.add_hint(variable, customer_lateness[customer])
        for vehicle_index, variable in cotwin.return_time.items():
            model.add_hint(variable, returns[vehicle_index])
        for vehicle_index, variable in cotwin.vehicle_lateness.items():
            model.add_hint(variable, vehicle_lateness[vehicle_index])
        model.add_hint(cotwin.hard_penalty, sum(overloads.values()))
        model.add_hint(
            cotwin.medium_penalty,
            sum(customer_lateness.values()) + sum(vehicle_lateness.values()),
        )
        model.add_hint(cotwin.distance, distance)
