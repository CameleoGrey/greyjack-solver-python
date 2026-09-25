"""Capacity-priced, capacity-relaxed facility assignment model."""

from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from typing import Callable

from ortools.sat.python import cp_model

from ..cotwin import CotFacilityLocation
from .DualMaster import Pattern


@dataclass(frozen=True)
class PriceVector:
    scale: int
    ticks: dict[int, int]

    def fractions(self) -> dict[int, Fraction]:
        return {fid: Fraction(value, self.scale) for fid, value in self.ticks.items()}


@dataclass(frozen=True)
class PricingResult:
    status: int
    assignment: dict[int, int] | None
    lower_bound: Fraction | None
    prices: PriceVector
    phase: str


class _PricingCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, variables, consumers, on_assignment):
        super().__init__()
        self.variables = variables
        self.consumers = consumers
        self.on_assignment = on_assignment

    def on_solution_callback(self) -> None:
        assignment = {
            cid: next(
                fid for fid, var in self.variables[cid].items() if self.value(var)
            )
            for cid in self.consumers
        }
        self.on_assignment(assignment)


class PricedSubproblem:
    def __init__(self, cotwin: CotFacilityLocation):
        self.cotwin = cotwin

    def checked_prices(self, prices: dict[int, Fraction | float]) -> PriceVector:
        facilities = self.cotwin.domain.facilities
        if any(not isfinite(float(value)) for value in prices.values()):
            raise ValueError("Nonfinite capacity price")
        for scale in (1000, 100, 10, 1):
            ticks = {
                f.id: max(0, round(prices.get(f.id, 0) * scale)) for f in facilities
            }
            if self.cotwin.mode == "penalized":
                ticks = {
                    fid: min(value, self.cotwin.hard_weight * scale)
                    for fid, value in ticks.items()
                }
            if self._objective_is_safe(scale, ticks):
                return PriceVector(scale, ticks)
        zeros = {f.id: 0 for f in facilities}
        if self._objective_is_safe(1, zeros):
            return PriceVector(1, zeros)
        raise ValueError("Dataset exceeds safe priced-model integer bounds")

    def _objective_is_safe(self, scale: int, ticks: dict[int, int]) -> bool:
        absolute_bound = sum(
            abs(2 * f.setup_cost * scale - ticks[f.id] * f.capacity)
            for f in self.cotwin.domain.facilities
        )
        absolute_bound += sum(
            abs(5 * self.cotwin.distances[c.id, f.id] * scale + ticks[f.id] * c.demand)
            for c in self.cotwin.domain.consumers
            for f in self.cotwin.domain.facilities
        )
        return absolute_bound <= cp_model.INT_MAX // 2

    def solve(
        self,
        prices: PriceVector,
        phase: str,
        seconds: float,
        workers: int,
        on_assignment: Callable[[dict[int, int]], None],
    ) -> PricingResult:
        if phase not in ("cost", "feasibility"):
            raise ValueError("Unknown pricing phase")
        model = cp_model.CpModel()
        assignments = self._add_customer_assignment(model)
        used = self._add_exact_usage(model, assignments)
        self._add_priced_objective(model, assignments, used, prices, phase)
        error = model.validate()
        if error:
            raise ValueError(f"Invalid priced model: {error}")
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = max(0.001, seconds)
        callback = _PricingCallback(
            assignments,
            tuple(c.id for c in self.cotwin.domain.consumers),
            on_assignment,
        )
        status = solver.solve(model, callback)
        if status == cp_model.MODEL_INVALID:
            raise ValueError(f"Invalid priced model: {model.validate()}")
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return PricingResult(status, None, None, prices, phase)
        assignment = {
            cid: next(fid for fid, var in row.items() if solver.value(var))
            for cid, row in assignments.items()
        }
        lower_bound = None
        if status == cp_model.OPTIMAL and phase == "cost":
            pattern = Pattern.from_assignment(self.cotwin, assignment)
            price_fractions = prices.fractions()
            lower_bound = pattern.base_cost + sum(
                price_fractions[fid] * residual for fid, residual in pattern.residuals
            )
        return PricingResult(status, assignment, lower_bound, prices, phase)

    def _add_customer_assignment(self, model):
        assignments = {}
        for consumer in self.cotwin.domain.consumers:
            row = {
                f.id: model.new_bool_var(f"assign_{consumer.id}_{f.id}")
                for f in self.cotwin.domain.facilities
            }
            model.add_exactly_one(row.values())
            assignments[consumer.id] = row
        return assignments

    def _add_exact_usage(self, model, assignments):
        used = {}
        for facility in self.cotwin.domain.facilities:
            fid = facility.id
            active = model.new_bool_var(f"used_{fid}")
            column = [assignments[c.id][fid] for c in self.cotwin.domain.consumers]
            for selected in column:
                model.add(selected <= active)
            model.add(active <= sum(column))
            used[fid] = active
        return used

    def _add_priced_objective(self, model, assignments, used, prices, phase):
        scale = prices.scale
        objective = sum(
            -prices.ticks[f.id] * f.capacity * used[f.id]
            + (2 * f.setup_cost * scale * used[f.id] if phase == "cost" else 0)
            for f in self.cotwin.domain.facilities
        )
        objective += sum(
            (
                prices.ticks[f.id] * c.demand
                + (
                    5 * self.cotwin.distances[c.id, f.id] * scale
                    if phase == "cost"
                    else 0
                )
            )
            * assignments[c.id][f.id]
            for c in self.cotwin.domain.consumers
            for f in self.cotwin.domain.facilities
        )
        model.minimize(objective)
