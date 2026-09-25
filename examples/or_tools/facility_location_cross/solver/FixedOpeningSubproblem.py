"""Fixed-opening assignment LP, capacity prices, and exact integer recourse."""

from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from typing import Callable

from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

from ..cotwin import CotFacilityLocation


class _AssignmentCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, variables, consumers, on_assignment):
        super().__init__()
        self.variables = variables
        self.consumers = consumers
        self.on_assignment = on_assignment

    def on_solution_callback(self) -> None:
        assignment = {
            cid: next(
                fid
                for fid, variable in self.variables[cid].items()
                if self.value(variable)
            )
            for cid in self.consumers
        }
        self.on_assignment(assignment)


@dataclass(frozen=True)
class DualCut:
    intercept: Fraction
    coefficients: dict[int, Fraction]

    def value(self, opened: set[int]) -> Fraction:
        return self.intercept + sum(self.coefficients[fid] for fid in opened)


@dataclass(frozen=True)
class FixedOpeningLPResult:
    status: int
    assignments: dict[int, int] | None
    cut: DualCut | None
    capacity_prices: dict[int, Fraction] | None


class FixedOpeningSubproblem:
    """Minimize assignment cost for a fixed opening pattern."""

    def __init__(self, cotwin: CotFacilityLocation):
        self.cotwin = cotwin

    def solve_lp(self, opened: set[int], seconds: float) -> FixedOpeningLPResult:
        solver = pywraplp.Solver.CreateSolver("GLOP")
        if solver is None:
            raise RuntimeError("OR-Tools GLOP backend is unavailable")
        solver.SetTimeLimit(max(1, int(1000 * seconds)))
        assignments = self._add_fractional_assignments(solver)
        self._add_customer_coverage(solver, assignments)
        activation, used, capacity = self._add_opening_and_capacity(
            solver, assignments, opened
        )
        self._add_distance_objective(solver, assignments)
        status = solver.Solve()
        if status != pywraplp.Solver.OPTIMAL:
            return FixedOpeningLPResult(status, None, None, None)
        integer_assignment = self._integral_assignment(assignments)
        dual_cut, prices = self._dual_cut(activation, used, capacity)
        return FixedOpeningLPResult(status, integer_assignment, dual_cut, prices)

    def _add_fractional_assignments(self, solver):
        # Only a nonnegative variable bound keeps the dual equations explicit.
        infinity = solver.infinity()
        return {
            (c.id, f.id): solver.NumVar(0, infinity, f"assign_{c.id}_{f.id}")
            for c in self.cotwin.domain.consumers
            for f in self.cotwin.domain.facilities
        }

    def _add_customer_coverage(self, solver, assignments):
        for consumer in self.cotwin.domain.consumers:
            row = solver.Constraint(1, 1, f"cover_{consumer.id}")
            for facility in self.cotwin.domain.facilities:
                row.SetCoefficient(assignments[consumer.id, facility.id], 1)

    def _add_opening_and_capacity(self, solver, assignments, opened):
        infinity = solver.infinity()
        activation = {}
        used = {}
        capacity = {}
        for facility in self.cotwin.domain.facilities:
            fid = facility.id
            for consumer in self.cotwin.domain.consumers:
                row = solver.Constraint(-infinity, int(fid in opened))
                row.SetCoefficient(assignments[consumer.id, fid], 1)
                activation[consumer.id, fid] = row

            used_row = solver.Constraint(int(fid in opened), infinity)
            cap_row = solver.Constraint(
                -infinity, facility.capacity * int(fid in opened)
            )
            for consumer in self.cotwin.domain.consumers:
                variable = assignments[consumer.id, fid]
                used_row.SetCoefficient(variable, 1)
                cap_row.SetCoefficient(variable, consumer.demand)
            if self.cotwin.mode == "penalized":
                overload = solver.NumVar(0, infinity, f"overload_{fid}")
                cap_row.SetCoefficient(overload, -1)
                solver.Objective().SetCoefficient(overload, self.cotwin.hard_weight)
            used[fid] = used_row
            capacity[fid] = cap_row
        return activation, used, capacity

    def _add_distance_objective(self, solver, assignments):
        objective = solver.Objective()
        for consumer in self.cotwin.domain.consumers:
            for facility in self.cotwin.domain.facilities:
                objective.SetCoefficient(
                    assignments[consumer.id, facility.id],
                    5 * self.cotwin.distances[consumer.id, facility.id],
                )
        objective.SetMinimization()

    def _integral_assignment(self, variables) -> dict[int, int] | None:
        result = {}
        for consumer in self.cotwin.domain.consumers:
            values = {
                f.id: variables[consumer.id, f.id].solution_value()
                for f in self.cotwin.domain.facilities
            }
            selected = [fid for fid, value in values.items() if value >= 1 - 1e-7]
            if len(selected) != 1 or any(
                abs(value) > 1e-7 for fid, value in values.items() if fid != selected[0]
            ):
                return None
            result[consumer.id] = selected[0]
        return result

    @staticmethod
    def _rational_nonnegative(value: float) -> Fraction:
        if not isfinite(value):
            raise RuntimeError("Nonfinite GLOP dual value")
        return Fraction(max(0.0, value)).limit_denominator(1_000_000)

    def _dual_cut(
        self, activation, used, capacity
    ) -> tuple[DualCut, dict[int, Fraction]]:
        """Rebuild a feasible rational dual, independent of GLOP rounding."""
        domain = self.cotwin.domain
        rho = {
            key: self._rational_nonnegative(-row.dual_value())
            for key, row in activation.items()
        }
        mu = {
            fid: self._rational_nonnegative(row.dual_value())
            for fid, row in used.items()
        }
        nu = {
            fid: self._rational_nonnegative(-row.dual_value())
            for fid, row in capacity.items()
        }
        if self.cotwin.mode == "penalized":
            nu = {fid: min(value, self.cotwin.hard_weight) for fid, value in nu.items()}

        # For each nonnegative x_cf, dual feasibility requires
        # alpha_c - rho_cf + mu_f - demand_c * nu_f <= 5 * distance_cf.
        alpha = {
            consumer.id: min(
                5 * self.cotwin.distances[consumer.id, facility.id]
                + rho[consumer.id, facility.id]
                - mu[facility.id]
                + consumer.demand * nu[facility.id]
                for facility in domain.facilities
            )
            for consumer in domain.consumers
        }
        coefficients = {
            facility.id: mu[facility.id]
            - sum(rho[consumer.id, facility.id] for consumer in domain.consumers)
            - facility.capacity * nu[facility.id]
            for facility in domain.facilities
        }
        return DualCut(sum(alpha.values(), Fraction(0)), coefficients), nu

    def solve_integer(
        self,
        opened: set[int],
        seconds: float,
        workers: int,
        on_assignment: Callable[[dict[int, int]], None],
    ) -> tuple[int, dict[int, int] | None, int | None]:
        model, variables = self._build_integer_model(opened)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = max(0.001, seconds)
        callback = _AssignmentCallback(
            variables,
            tuple(c.id for c in self.cotwin.domain.consumers),
            on_assignment,
        )
        status = solver.solve(model, callback)
        if status == cp_model.MODEL_INVALID:
            raise ValueError(f"Invalid fixed-opening model: {model.validate()}")
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return status, None, None
        assignment = {
            cid: next(fid for fid, var in row.items() if solver.value(var))
            for cid, row in variables.items()
        }
        return status, assignment, self._assignment_cost(assignment)

    def _build_integer_model(
        self, opened: set[int]
    ) -> tuple[cp_model.CpModel, dict[int, dict[int, cp_model.IntVar]]]:
        model = cp_model.CpModel()
        facilities = [f for f in self.cotwin.domain.facilities if f.id in opened]
        variables = self._add_customer_assignment(model, facilities)
        overloads = self._add_usage_and_capacity(model, facilities, variables)
        self._add_objective(model, facilities, variables, overloads)
        error = model.validate()
        if error:
            raise ValueError(f"Invalid fixed-opening model: {error}")
        return model, variables

    def _add_customer_assignment(self, model, facilities):
        variables = {}
        for consumer in self.cotwin.domain.consumers:
            row = {
                facility.id: model.new_bool_var(f"assign_{consumer.id}_{facility.id}")
                for facility in facilities
            }
            model.add_exactly_one(row.values())
            variables[consumer.id] = row
        return variables

    def _add_usage_and_capacity(self, model, facilities, variables):
        total_demand = sum(c.demand for c in self.cotwin.domain.consumers)
        overloads = []
        for facility in facilities:
            fid = facility.id
            model.add(
                sum(variables[c.id][fid] for c in self.cotwin.domain.consumers) >= 1
            )
            load = sum(
                c.demand * variables[c.id][fid] for c in self.cotwin.domain.consumers
            )
            if self.cotwin.mode == "strict":
                model.add(load <= facility.capacity)
            else:
                overload = model.new_int_var(
                    0, max(0, total_demand - facility.capacity), f"overload_{fid}"
                )
                model.add(overload >= load - facility.capacity)
                overloads.append(overload)
        return overloads

    def _add_objective(self, model, facilities, variables, overloads):
        distance = sum(
            5 * self.cotwin.distances[c.id, f.id] * variables[c.id][f.id]
            for c in self.cotwin.domain.consumers
            for f in facilities
        )
        model.minimize(distance + self.cotwin.hard_weight * sum(overloads))

    def _assignment_cost(self, assignment: dict[int, int]) -> int:
        loads = {f.id: 0 for f in self.cotwin.domain.facilities}
        distance = 0
        for consumer in self.cotwin.domain.consumers:
            fid = assignment[consumer.id]
            loads[fid] += consumer.demand
            distance += 5 * self.cotwin.distances[consumer.id, fid]
        overload = sum(
            max(0, loads[f.id] - f.capacity) for f in self.cotwin.domain.facilities
        )
        return distance + self.cotwin.hard_weight * overload
