"""Standalone complete-route seed; CP-SAT is used only if greedy is not strict-feasible."""

from typing import Callable

from ortools.sat.python import cp_model

from ..cotwin import CotVRP


class SeedSolver:
    @staticmethod
    def greedy(cotwin: CotVRP) -> tuple[tuple[int, ...], ...]:
        domain = cotwin.domain
        routes: list[list[int]] = [[] for _ in domain.vehicles]
        loads = [0] * len(domain.vehicles)
        remaining = set(cotwin.customer_ids)
        indices = domain.index_by_id
        locations = domain.location_by_id
        for vehicle_index, vehicle in enumerate(domain.vehicles):
            current = vehicle.depot_id
            while True:
                fitting = [
                    customer
                    for customer in remaining
                    if loads[vehicle_index] + locations[customer].demand
                    <= vehicle.capacity
                ]
                if not fitting:
                    break
                customer = min(
                    fitting,
                    key=lambda candidate: (
                        domain.distance_matrix[indices[current]][indices[candidate]],
                        candidate,
                    ),
                )
                routes[vehicle_index].append(customer)
                loads[vehicle_index] += locations[customer].demand
                remaining.remove(customer)
                current = customer
        for customer in sorted(remaining):
            vehicle_index = min(
                range(len(domain.vehicles)),
                key=lambda index: (
                    max(
                        0,
                        loads[index]
                        + locations[customer].demand
                        - domain.vehicles[index].capacity,
                    )
                    - max(0, loads[index] - domain.vehicles[index].capacity),
                    domain.distance_matrix[
                        indices[routes[index][-1]]
                        if routes[index]
                        else indices[domain.vehicles[index].depot_id]
                    ][indices[customer]],
                    index,
                ),
            )
            routes[vehicle_index].append(customer)
            loads[vehicle_index] += locations[customer].demand
        return tuple(tuple(route) for route in routes)

    def solve(
        self,
        cotwin: CotVRP,
        seconds: float,
        workers: int = 1,
        *,
        on_solution: Callable[[tuple[int, int, int]], None] | None = None,
    ) -> tuple[tuple[tuple[int, ...], ...] | None, bool]:
        greedy = self.greedy(cotwin)
        if cotwin.mode == "penalized" or self._strict_valid(cotwin, greedy):
            if on_solution is not None:
                on_solution(self._score_routes(cotwin, greedy))
            return greedy, False
        if seconds <= 0:
            return None, False
        domain = cotwin.domain
        customers = cotwin.customer_ids
        if not customers:
            return tuple(() for _ in domain.vehicles), False
        if any(
            domain.location_by_id[c].demand
            > max(vehicle.capacity for vehicle in domain.vehicles)
            for c in customers
        ):
            return None, True
        if domain.time_windowed and any(
            domain.location_by_id[c].time_window_start
            + domain.location_by_id[c].service_time
            > domain.location_by_id[c].time_window_end
            for c in customers
        ):
            return None, True
        model = cp_model.CpModel()
        used = {}
        assigned = {}
        arcs = {}
        nodes = {customer: index for index, customer in enumerate(customers, 1)}
        for vehicle_index, vehicle in enumerate(domain.vehicles):
            depot = vehicle.depot_id
            used[vehicle_index] = model.new_bool_var(f"used_{vehicle_index}")
            for customer in customers:
                assigned[vehicle_index, customer] = model.new_bool_var(
                    f"assigned_{vehicle_index}_{customer}"
                )
                arcs[vehicle_index, depot, customer] = model.new_bool_var(
                    f"start_{vehicle_index}_{customer}"
                )
                arcs[vehicle_index, customer, depot] = model.new_bool_var(
                    f"end_{vehicle_index}_{customer}"
                )
                for other in customers:
                    if other != customer:
                        arcs[vehicle_index, customer, other] = model.new_bool_var(
                            f"arc_{vehicle_index}_{customer}_{other}"
                        )
            model.add(
                sum(
                    domain.location_by_id[c].demand * assigned[vehicle_index, c]
                    for c in customers
                )
                <= vehicle.capacity
            )
            circuit = [(0, 0, used[vehicle_index].Not())]
            for customer in customers:
                node = nodes[customer]
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
        for customer in customers:
            model.add_exactly_one(
                assigned[v, customer] for v in range(len(domain.vehicles))
            )
        starts = {}
        if domain.time_windowed:
            time_bound = max(
                [
                    *(v.work_day_start for v in domain.vehicles),
                    *(domain.location_by_id[c].time_window_start for c in customers),
                ]
            ) + sum(domain.location_by_id[c].service_time for c in customers)
            if time_bound > cp_model.INT_MAX // 4:
                raise ValueError("Dataset exceeds safe CP-SAT seed time bounds")
            for customer in customers:
                location = domain.location_by_id[customer]
                starts[customer] = model.new_int_var(
                    location.time_window_start,
                    min(time_bound, location.time_window_end - location.service_time),
                    f"service_start_{customer}",
                )
            for vehicle_index, vehicle in enumerate(domain.vehicles):
                depot = vehicle.depot_id
                for customer in customers:
                    location = domain.location_by_id[customer]
                    model.add(
                        starts[customer] >= vehicle.work_day_start
                    ).only_enforce_if(arcs[vehicle_index, depot, customer])
                    model.add(
                        starts[customer] + location.service_time <= vehicle.work_day_end
                    ).only_enforce_if(arcs[vehicle_index, customer, depot])
                    for other in customers:
                        if other != customer:
                            model.add(
                                starts[other]
                                >= starts[customer] + location.service_time
                            ).only_enforce_if(arcs[vehicle_index, customer, other])
        indices = domain.index_by_id
        model.minimize(
            sum(
                domain.distance_matrix[indices[source]][indices[target]] * var
                for (_, source, target), var in arcs.items()
            )
        )
        selected_arcs = set()
        selected_assignments = set()
        hint_starts = {}
        for vehicle_index, route in enumerate(greedy):
            depot = domain.vehicles[vehicle_index].depot_id
            if route:
                selected_arcs.add((vehicle_index, depot, route[0]))
                selected_arcs.add((vehicle_index, route[-1], depot))
                selected_arcs.update(
                    (vehicle_index, left, right)
                    for left, right in zip(route, route[1:])
                )
            selected_assignments.update((vehicle_index, c) for c in route)
            clock = domain.vehicles[vehicle_index].work_day_start
            for customer in route:
                if domain.time_windowed:
                    location = domain.location_by_id[customer]
                    earliest = max(clock, location.time_window_start)
                    hint_starts[customer] = min(
                        earliest, location.time_window_end - location.service_time
                    )
                    clock = earliest + location.service_time
        for key, variable in arcs.items():
            model.add_hint(variable, int(key in selected_arcs))
        for key, variable in assigned.items():
            model.add_hint(variable, int(key in selected_assignments))
        for vehicle_index, variable in used.items():
            model.add_hint(variable, int(bool(greedy[vehicle_index])))
        for customer, variable in starts.items():
            model.add_hint(variable, hint_starts[customer])
        error = model.validate()
        if error:
            raise ValueError(f"Invalid CP-SAT seed model: {error}")
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = seconds
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = 0
        solver.parameters.cp_model_presolve = False

        def decode(value):
            successors = {
                (vehicle, source): target
                for (vehicle, source, target), var in arcs.items()
                if value(var)
            }
            routes = []
            for vehicle_index, vehicle in enumerate(domain.vehicles):
                route = []
                if value(used[vehicle_index]):
                    current = vehicle.depot_id
                    while True:
                        current = successors[vehicle_index, current]
                        if current == vehicle.depot_id:
                            break
                        route.append(current)
                        if len(route) > len(customers):
                            raise RuntimeError("Seed route contains a cycle")
                routes.append(tuple(route))
            return tuple(routes)

        if on_solution is None:
            status = solver.solve(model)
        else:

            class SeedCallback(cp_model.CpSolverSolutionCallback):
                def on_solution_callback(self) -> None:
                    candidate = decode(self.value)
                    if not SeedSolver._strict_valid(cotwin, candidate):
                        raise RuntimeError(
                            "CP-SAT seed callback returned invalid routes"
                        )
                    on_solution(SeedSolver._score_routes(cotwin, candidate))

            status = solver.solve(model, SeedCallback())
        if status == cp_model.INFEASIBLE:
            return None, True
        if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            return None, False
        result = decode(solver.value)
        if not self._strict_valid(cotwin, result):
            raise RuntimeError("CP-SAT seed failed independent route validation")
        return result, False

    @staticmethod
    def _score_routes(
        cotwin: CotVRP, routes: tuple[tuple[int, ...], ...]
    ) -> tuple[int, int, int]:
        groups = {
            vehicle_index: group_index
            for group_index, group in enumerate(cotwin.groups)
            for vehicle_index in group.vehicle_indices
        }
        columns = [
            cotwin.make_column(groups[index], route)
            for index, route in enumerate(routes)
            if route
        ]
        return tuple(sum(column.score[i] for column in columns) for i in range(3))

    @staticmethod
    def _strict_valid(cotwin: CotVRP, routes: tuple[tuple[int, ...], ...]) -> bool:
        if len(routes) != len(cotwin.domain.vehicles):
            return False
        covered = [customer for route in routes for customer in route]
        if len(covered) != len(cotwin.customer_ids) or set(covered) != set(
            cotwin.customer_ids
        ):
            return False
        groups = {
            vehicle_index: group_index
            for group_index, group in enumerate(cotwin.groups)
            for vehicle_index in group.vehicle_indices
        }
        try:
            for vehicle_index, route in enumerate(routes):
                if route:
                    cotwin.make_column(groups[vehicle_index], route)
        except ValueError:
            return False
        return True
