"""Assignment LP and its verified affine Benders lower bound."""

from dataclasses import dataclass
from fractions import Fraction
from math import isfinite

from ortools.linear_solver import pywraplp

from ..cotwin import CotFacilityLocation


@dataclass(frozen=True)
class DualCut:
    intercept: Fraction
    coefficients: dict[int, Fraction]

    def value(self, opened: set[int]) -> Fraction:
        return self.intercept + sum(self.coefficients[fid] for fid in opened)


@dataclass(frozen=True)
class AssignmentLPResult:
    status: int
    assignments: dict[int, int] | None
    cut: DualCut | None


class AssignmentSubproblem:
    """Minimize assignment cost for a fixed opening pattern with GLOP."""

    def __init__(self, cotwin: CotFacilityLocation):
        self.cotwin = cotwin

    def solve(self, opened: set[int], seconds: float) -> AssignmentLPResult:
        solver = pywraplp.Solver.CreateSolver("GLOP")
        if solver is None:
            raise RuntimeError("OR-Tools GLOP backend is unavailable")
        solver.SetTimeLimit(max(1, int(1000 * seconds)))
        infinity = solver.infinity()
        domain = self.cotwin.domain

        # x_cf is the fraction of consumer c assigned to facility f. Keeping
        # its only variable bound at zero makes the dual equations explicit.
        assignments = {
            (c.id, f.id): solver.NumVar(0, infinity, f"assign_{c.id}_{f.id}")
            for c in domain.consumers
            for f in domain.facilities
        }
        for consumer in domain.consumers:
            row = solver.Constraint(1, 1, f"cover_{consumer.id}")
            for facility in domain.facilities:
                row.SetCoefficient(assignments[consumer.id, facility.id], 1)

        activation = {}
        used = {}
        capacity = {}
        for facility in domain.facilities:
            fid = facility.id
            for consumer in domain.consumers:
                row = solver.Constraint(-infinity, int(fid in opened))
                row.SetCoefficient(assignments[consumer.id, fid], 1)
                activation[consumer.id, fid] = row

            used_row = solver.Constraint(int(fid in opened), infinity)
            cap_row = solver.Constraint(
                -infinity, facility.capacity * int(fid in opened)
            )
            for consumer in domain.consumers:
                variable = assignments[consumer.id, fid]
                used_row.SetCoefficient(variable, 1)
                cap_row.SetCoefficient(variable, consumer.demand)
            if self.cotwin.mode == "penalized":
                overload = solver.NumVar(0, infinity, f"overload_{fid}")
                cap_row.SetCoefficient(overload, -1)
                solver.Objective().SetCoefficient(overload, self.cotwin.hard_weight)
            used[fid] = used_row
            capacity[fid] = cap_row

        objective = solver.Objective()
        for consumer in domain.consumers:
            for facility in domain.facilities:
                objective.SetCoefficient(
                    assignments[consumer.id, facility.id],
                    5 * self.cotwin.distances[consumer.id, facility.id],
                )
        objective.SetMinimization()
        status = solver.Solve()
        if status != pywraplp.Solver.OPTIMAL:
            return AssignmentLPResult(status, None, None)
        integer_assignment = self._integral_assignment(assignments)
        dual_cut = self._dual_cut(activation, used, capacity)
        return AssignmentLPResult(status, integer_assignment, dual_cut)

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

    def _dual_cut(self, activation, used, capacity) -> DualCut:
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
        return DualCut(sum(alpha.values(), Fraction(0)), coefficients)
