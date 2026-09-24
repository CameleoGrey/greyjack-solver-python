from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from ..cotwin import CotVRP
from ..domain import VehicleRoutingPlan


@dataclass(frozen=True)
class _ModelFacts:
    location_ids: tuple[int, ...]
    customers: tuple[int, ...]
    depots: tuple[int, ...]
    vehicle_count: int
    distance_bound: int
    hard_bound: int
    time_bound: int
    medium_bound: int
    medium_weight: int
    hard_weight: int


@dataclass
class _ModelState:
    model: cp_model.CpModel
    arcs: dict[tuple[int, int, int], cp_model.IntVar] = field(default_factory=dict)
    assigned: dict[tuple[int, int], cp_model.IntVar] = field(default_factory=dict)
    used: dict[int, cp_model.IntVar] = field(default_factory=dict)
    order: dict[int, cp_model.IntVar] = field(default_factory=dict)
    overloads: dict[int, cp_model.IntVar] = field(default_factory=dict)
    arrival: dict[int, cp_model.IntVar] = field(default_factory=dict)
    service_start: dict[int, cp_model.IntVar] = field(default_factory=dict)
    customer_lateness: dict[int, cp_model.IntVar] = field(default_factory=dict)
    return_time: dict[int, cp_model.IntVar] = field(default_factory=dict)
    vehicle_lateness: dict[int, cp_model.IntVar] = field(default_factory=dict)


class CotwinBuilder:
    def __init__(
        self,
        use_greedy_hints: bool = True,
        *,
        mode: str = "penalized",
        formulation: str = "mtz",
    ):
        if mode not in ("penalized", "strict"):
            raise ValueError("mode must be 'penalized' or 'strict'")
        if formulation not in ("mtz", "circuit"):
            raise ValueError("formulation must be 'mtz' or 'circuit'")
        self.use_greedy_hints = use_greedy_hints
        self.mode = mode
        self.formulation = formulation

    def build_cotwin(self, domain: VehicleRoutingPlan) -> CotVRP:
        domain.validate()
        facts = self._checked_model_facts(domain)
        state = _ModelState(cp_model.CpModel())
        self._add_route_variables(state, facts)
        self._add_route_constraints(state, facts)
        self._add_capacity_penalties(state, facts, domain)
        self._add_time_penalties(state, facts, domain)
        hard, medium, distance = self._add_objective(state, facts, domain)

        cotwin = CotVRP(
            state.model,
            state.arcs,
            state.assigned,
            state.used,
            state.order,
            state.overloads,
            state.arrival,
            state.service_start,
            state.customer_lateness,
            state.return_time,
            state.vehicle_lateness,
            hard,
            medium,
            distance,
            facts.location_ids,
            facts.customers,
            facts.depots,
            facts.medium_weight,
            facts.hard_weight,
            self.mode,
        )
        if self.use_greedy_hints:
            self._add_greedy_hints(domain, cotwin)
        validation_error = state.model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        return cotwin

    def _checked_model_facts(self, domain: VehicleRoutingPlan) -> _ModelFacts:
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
        return _ModelFacts(
            location_ids,
            customers,
            depots,
            vehicle_count,
            distance_bound,
            hard_bound,
            time_bound,
            medium_bound,
            medium_weight,
            hard_weight,
        )

    def _add_route_variables(self, state: _ModelState, facts: _ModelFacts) -> None:
        model = state.model
        customer_count = len(facts.customers)
        if self.formulation == "mtz":
            state.order = {
                index: model.new_int_var(1, customer_count, f"order_{index}")
                for index in facts.customers
            }
        for vehicle_index, depot in enumerate(facts.depots):
            state.used[vehicle_index] = model.new_bool_var(f"used_{vehicle_index}")
            for customer in facts.customers:
                state.assigned[vehicle_index, customer] = model.new_bool_var(
                    f"assigned_{vehicle_index}_{customer}"
                )
                state.arcs[vehicle_index, depot, customer] = model.new_bool_var(
                    f"arc_{vehicle_index}_{depot}_{customer}"
                )
                state.arcs[vehicle_index, customer, depot] = model.new_bool_var(
                    f"arc_{vehicle_index}_{customer}_{depot}"
                )
                for other in facts.customers:
                    if other != customer:
                        state.arcs[vehicle_index, customer, other] = model.new_bool_var(
                            f"arc_{vehicle_index}_{customer}_{other}"
                        )

    def _add_route_constraints(self, state: _ModelState, facts: _ModelFacts) -> None:
        model = state.model
        arcs, assigned, used, order = (
            state.arcs,
            state.assigned,
            state.used,
            state.order,
        )
        customers = facts.customers
        for customer in customers:
            model.add_exactly_one(
                assigned[v, customer] for v in range(facts.vehicle_count)
            )
        if self.formulation == "circuit":
            # Each vehicle has its own depot at node 0; other depot indices are
            # deliberately omitted from this dense, vehicle-local graph.
            nodes = {customer: index for index, customer in enumerate(customers, 1)}
            for vehicle_index, depot in enumerate(facts.depots):
                circuit = [(0, 0, used[vehicle_index].Not())]
                for customer in customers:
                    node = nodes[customer]
                    # The depot self-loop alone does not prevent a separate
                    # customer cycle when this vehicle is marked unused.
                    model.add_implication(
                        assigned[vehicle_index, customer], used[vehicle_index]
                    )
                    circuit.extend(
                        (
                            (node, node, assigned[vehicle_index, customer].Not()),
                            (0, node, arcs[vehicle_index, depot, customer]),
                            (node, 0, arcs[vehicle_index, customer, depot]),
                        )
                    )
                    circuit.extend(
                        (node, nodes[other], arcs[vehicle_index, customer, other])
                        for other in customers
                        if other != customer
                    )
                model.add_circuit(circuit)
            return
        for vehicle_index, depot in enumerate(facts.depots):
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
                        # MTZ order rises on each chosen arc, excluding subtours.
                        model.add(order[other] >= order[customer] + 1).only_enforce_if(
                            arcs[vehicle_index, customer, other]
                        )

    @staticmethod
    def _add_capacity_penalties(
        state: _ModelState, facts: _ModelFacts, domain: VehicleRoutingPlan
    ) -> None:
        model = state.model
        for vehicle_index, vehicle in enumerate(domain.vehicles):
            load = sum(
                domain.locations[customer].demand
                * state.assigned[vehicle_index, customer]
                for customer in facts.customers
            )
            overload = model.new_int_var(
                0, facts.hard_bound, f"overload_{vehicle_index}"
            )
            model.add_max_equality(overload, [0, load - vehicle.capacity])
            state.overloads[vehicle_index] = overload

    @staticmethod
    def _add_time_penalties(
        state: _ModelState, facts: _ModelFacts, domain: VehicleRoutingPlan
    ) -> None:
        if not domain.time_windowed:
            return
        model = state.model
        for customer in facts.customers:
            location = domain.locations[customer]
            state.arrival[customer] = model.new_int_var(
                0, facts.time_bound, f"arrival_{customer}"
            )
            state.service_start[customer] = model.new_int_var(
                0, facts.time_bound, f"service_start_{customer}"
            )
            model.add_max_equality(
                state.service_start[customer],
                [state.arrival[customer], location.time_window_start],
            )
            state.customer_lateness[customer] = model.new_int_var(
                0,
                max(0, facts.time_bound - location.time_window_end),
                f"lateness_{customer}",
            )
            model.add_max_equality(
                state.customer_lateness[customer],
                [
                    0,
                    state.service_start[customer]
                    + location.service_time
                    - location.time_window_end,
                ],
            )
        for vehicle_index, vehicle in enumerate(domain.vehicles):
            depot = facts.depots[vehicle_index]
            state.return_time[vehicle_index] = model.new_int_var(
                0, facts.time_bound, f"return_{vehicle_index}"
            )
            model.add(
                state.return_time[vehicle_index] == vehicle.work_day_start
            ).only_enforce_if(state.used[vehicle_index].Not())
            state.vehicle_lateness[vehicle_index] = model.new_int_var(
                0,
                max(0, facts.time_bound - vehicle.work_day_end),
                f"workday_lateness_{vehicle_index}",
            )
            model.add_max_equality(
                state.vehicle_lateness[vehicle_index],
                [0, state.return_time[vehicle_index] - vehicle.work_day_end],
            )
            for customer in facts.customers:
                model.add(
                    state.arrival[customer] == vehicle.work_day_start
                ).only_enforce_if(state.arcs[vehicle_index, depot, customer])
                model.add(
                    state.return_time[vehicle_index]
                    == state.service_start[customer]
                    + domain.locations[customer].service_time
                ).only_enforce_if(state.arcs[vehicle_index, customer, depot])
                for other in facts.customers:
                    if other != customer:
                        # The source clock advances by service, not travel time.
                        model.add(
                            state.arrival[other]
                            == state.service_start[customer]
                            + domain.locations[customer].service_time
                        ).only_enforce_if(state.arcs[vehicle_index, customer, other])

    def _add_objective(
        self, state: _ModelState, facts: _ModelFacts, domain: VehicleRoutingPlan
    ) -> tuple[cp_model.IntVar, cp_model.IntVar, cp_model.IntVar]:
        model = state.model
        hard = model.new_int_var(0, facts.hard_bound, "hard_penalty")
        medium = model.new_int_var(0, facts.medium_bound, "medium_penalty")
        distance = model.new_int_var(0, facts.distance_bound, "distance")
        model.add(hard == sum(state.overloads.values()))
        model.add(
            medium
            == sum(state.customer_lateness.values())
            + sum(state.vehicle_lateness.values())
        )
        model.add(
            distance
            == sum(
                domain.distance_matrix[source][target] * variable
                for (_, source, target), variable in state.arcs.items()
            )
        )
        if self.mode == "strict":
            for penalty in (
                *state.overloads.values(),
                *state.customer_lateness.values(),
                *state.vehicle_lateness.values(),
            ):
                model.add(penalty == 0)
            model.add(hard == 0)
            model.add(medium == 0)
            model.minimize(distance)
        else:
            # Checked weights preserve hard, then medium, then distance order.
            model.minimize(
                facts.hard_weight * hard + facts.medium_weight * medium + distance
            )
        return hard, medium, distance

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
