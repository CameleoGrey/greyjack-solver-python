"""Exact elementary-route pricing with SCIP, subject to solver tolerances."""

from dataclasses import dataclass

from ortools.linear_solver import pywraplp

from ..cotwin import CotVRP, RouteColumn


@dataclass(frozen=True)
class PriceResult:
    column: RouteColumn | None
    reduced_cost: float | None
    optimal: bool
    status: str


class PricingSolver:
    def price(
        self,
        cotwin: CotVRP,
        group_index: int,
        customer_duals: dict[int, float],
        group_dual: float,
        components: tuple[float, float, float],
        seconds: float,
    ) -> PriceResult:
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if solver is None:
            raise RuntimeError("OR-Tools SCIP pricing backend is unavailable")
        solver.SetTimeLimit(max(1, int(seconds * 1000)))
        solver.SetNumThreads(1)
        customers = cotwin.customer_ids
        group = cotwin.groups[group_index]
        domain = cotwin.domain
        locations = domain.location_by_id
        indices = domain.index_by_id
        n = len(customers)
        if not n:
            return PriceResult(None, None, True, "EMPTY")

        used = solver.BoolVar("used")
        solver.Add(used == 1)
        selected = {
            customer: solver.BoolVar(f"visit_{customer}") for customer in customers
        }
        order = {
            customer: solver.NumVar(0, n, f"order_{customer}") for customer in customers
        }
        arcs: dict[tuple[int | None, int | None], pywraplp.Variable] = {}
        for customer in customers:
            arcs[None, customer] = solver.BoolVar(f"depot_to_{customer}")
            arcs[customer, None] = solver.BoolVar(f"{customer}_to_depot")
            for other in customers:
                if customer != other:
                    arcs[customer, other] = solver.BoolVar(f"{customer}_to_{other}")
        solver.Add(sum(arcs[None, c] for c in customers) == used)
        solver.Add(sum(arcs[c, None] for c in customers) == used)
        for customer in customers:
            solver.Add(
                arcs[None, customer]
                + sum(arcs[other, customer] for other in customers if other != customer)
                == selected[customer]
            )
            solver.Add(
                arcs[customer, None]
                + sum(arcs[customer, other] for other in customers if other != customer)
                == selected[customer]
            )
            solver.Add(order[customer] >= selected[customer])
            solver.Add(order[customer] <= n * selected[customer])
            for other in customers:
                if customer != other:
                    solver.Add(
                        order[other]
                        >= order[customer] + 1 - (n + 1) * (1 - arcs[customer, other])
                    )

        hard_coefficient, medium_coefficient, distance_coefficient = components
        load = sum(locations[c].demand * selected[c] for c in customers)
        overload = None
        if cotwin.mode == "strict":
            solver.Add(load <= group.capacity)
        elif hard_coefficient > 0:
            overload = solver.NumVar(
                0, sum(locations[c].demand for c in customers), "overload"
            )
            solver.Add(overload >= load - group.capacity)

        customer_lateness = {}
        workday_lateness = None
        if domain.time_windowed and (cotwin.mode == "strict" or medium_coefficient > 0):
            time_bound = max(
                group.work_day_start,
                *(locations[c].time_window_start for c in customers),
            ) + sum(locations[c].service_time for c in customers)
            big_m = (
                2 * time_bound
                + max(locations[c].service_time for c in customers)
                + max(locations[c].time_window_end for c in customers)
                + 1
            )
            starts = {
                c: solver.NumVar(0, time_bound, f"service_start_{c}") for c in customers
            }
            for customer in customers:
                location = locations[customer]
                solver.Add(starts[customer] <= time_bound * selected[customer])
                solver.Add(
                    starts[customer] >= group.work_day_start * selected[customer]
                )
                solver.Add(
                    starts[customer] >= location.time_window_start * selected[customer]
                )
                for other in customers:
                    if customer != other:
                        solver.Add(
                            starts[other]
                            >= starts[customer]
                            + location.service_time
                            - big_m * (1 - arcs[customer, other])
                        )
                if cotwin.mode == "strict":
                    solver.Add(
                        starts[customer] + location.service_time
                        <= location.time_window_end + big_m * (1 - selected[customer])
                    )
                    solver.Add(
                        starts[customer] + location.service_time
                        <= group.work_day_end + big_m * (1 - arcs[customer, None])
                    )
                else:
                    late = solver.NumVar(0, big_m, f"late_{customer}")
                    solver.Add(late <= big_m * selected[customer])
                    solver.Add(
                        late
                        >= starts[customer]
                        + location.service_time
                        - location.time_window_end
                        - big_m * (1 - selected[customer])
                    )
                    customer_lateness[customer] = late
            if cotwin.mode == "penalized":
                workday_lateness = solver.NumVar(0, big_m, "workday_late")
                for customer in customers:
                    solver.Add(
                        workday_lateness
                        >= starts[customer]
                        + locations[customer].service_time
                        - group.work_day_end
                        - big_m * (1 - arcs[customer, None])
                    )

        objective = solver.Objective()
        objective.SetMinimization()
        objective.SetCoefficient(used, -group_dual)
        for customer, variable in selected.items():
            objective.SetCoefficient(variable, -customer_duals[customer])
        for (source, target), variable in arcs.items():
            left = group.depot_id if source is None else source
            right = group.depot_id if target is None else target
            objective.SetCoefficient(
                variable,
                distance_coefficient
                * domain.distance_matrix[indices[left]][indices[right]],
            )
        if overload is not None:
            objective.SetCoefficient(overload, hard_coefficient)
        if medium_coefficient > 0:
            for variable in customer_lateness.values():
                objective.SetCoefficient(variable, medium_coefficient)
            if workday_lateness is not None:
                objective.SetCoefficient(workday_lateness, medium_coefficient)

        status = solver.Solve()
        if status == pywraplp.Solver.INFEASIBLE:
            return PriceResult(None, None, True, "INFEASIBLE")
        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            return PriceResult(None, None, False, "UNKNOWN")
        successors = {
            source: target
            for (source, target), variable in arcs.items()
            if variable.solution_value() > 0.5
        }
        route = []
        current = None
        while True:
            if current not in successors:
                raise RuntimeError("Pricing produced an open route")
            current = successors[current]
            if current is None:
                break
            route.append(current)
            if len(route) > n:
                raise RuntimeError("Pricing produced a customer cycle")
        column = cotwin.make_column(group_index, tuple(route))
        reduced = (
            sum(a * b for a, b in zip(components, column.score))
            - sum(customer_duals[c] for c in route)
            - group_dual
        )
        return PriceResult(
            column,
            reduced,
            status == pywraplp.Solver.OPTIMAL,
            "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE",
        )
