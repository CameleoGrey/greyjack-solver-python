"""Restricted Dantzig-Wolfe master for the Lagrangian dual."""

from dataclasses import dataclass
from time import monotonic

from ortools.linear_solver import pywraplp

from ..cotwin import CotFacilityLocation


@dataclass(frozen=True)
class Pattern:
    assignment: tuple[tuple[int, int], ...]
    base_cost: int
    residuals: tuple[tuple[int, int], ...]

    @classmethod
    def from_assignment(cls, cotwin: CotFacilityLocation, assignment: dict[int, int]):
        consumers = cotwin.domain.consumers
        facilities = cotwin.domain.facilities
        if set(assignment) != {c.id for c in consumers}:
            raise ValueError("Dual pattern does not cover every consumer")
        known = {f.id for f in facilities}
        if any(fid not in known for fid in assignment.values()):
            raise ValueError("Dual pattern references an unknown facility")
        opened = set(assignment.values())
        loads = {f.id: 0 for f in facilities}
        distance = 0
        for consumer in consumers:
            fid = assignment[consumer.id]
            loads[fid] += consumer.demand
            distance += 5 * cotwin.distances[consumer.id, fid]
        setup = 2 * sum(f.setup_cost for f in facilities if f.id in opened)
        residuals = tuple(
            (f.id, loads[f.id] - f.capacity * int(f.id in opened)) for f in facilities
        )
        return cls(
            tuple((c.id, assignment[c.id]) for c in consumers),
            setup + distance,
            residuals,
        )

    def assignments(self) -> dict[int, int]:
        return dict(self.assignment)


@dataclass(frozen=True)
class MasterResult:
    phase: str
    prices: dict[int, float]
    value: float


class DualMaster:
    """Solve a restricted master; its value alone is not a global bound."""

    def __init__(self, cotwin: CotFacilityLocation):
        self.cotwin = cotwin
        self.patterns: dict[tuple[tuple[int, int], ...], Pattern] = {}
        self.solves = 0

    def add_pattern(self, assignment: dict[int, int]) -> bool:
        pattern = Pattern.from_assignment(self.cotwin, assignment)
        if pattern.assignment in self.patterns:
            return False
        self.patterns[pattern.assignment] = pattern
        return True

    def solve(self, seconds: float) -> MasterResult | None:
        if not self.patterns or seconds <= 0:
            return None
        if self.cotwin.mode == "strict":
            deadline = monotonic() + seconds
            phase_one = self._solve_phase("feasibility", seconds)
            if phase_one is None or phase_one.value > 1e-7:
                return phase_one
            remaining = deadline - monotonic()
            return self._solve_phase("cost", remaining) if remaining > 0 else None
        return self._solve_phase("cost", seconds)

    def _solve_phase(self, phase: str, seconds: float) -> MasterResult | None:
        solver = pywraplp.Solver.CreateSolver("GLOP")
        if solver is None:
            raise RuntimeError("OR-Tools GLOP backend is unavailable")
        solver.SetTimeLimit(max(1, int(1000 * seconds)))
        rows = self._add_capacity_rows(solver)
        convexity = solver.Constraint(1, 1, "one_complete_pattern")
        objective = solver.Objective()
        objective.SetMinimization()
        self._add_pattern_columns(solver, objective, convexity, rows, phase)
        self._add_artificial_overload(solver, objective, rows, phase)
        self.solves += 1
        if solver.Solve() != pywraplp.Solver.OPTIMAL:
            return None
        limit = 1 if phase == "feasibility" else self.cotwin.hard_weight
        prices = {fid: max(0.0, -row.dual_value()) for fid, row in rows.items()}
        if self.cotwin.mode == "penalized" or phase == "feasibility":
            prices = {fid: min(limit, value) for fid, value in prices.items()}
        return MasterResult(phase, prices, objective.Value())

    def _add_capacity_rows(self, solver):
        return {
            f.id: solver.Constraint(-solver.infinity(), 0, f"capacity_{f.id}")
            for f in self.cotwin.domain.facilities
        }

    def _add_pattern_columns(self, solver, objective, convexity, rows, phase):
        for index, pattern in enumerate(self.patterns.values()):
            column = solver.NumVar(0, solver.infinity(), f"pattern_{index}")
            convexity.SetCoefficient(column, 1)
            for fid, residual in pattern.residuals:
                rows[fid].SetCoefficient(column, residual)
            if phase == "cost":
                objective.SetCoefficient(column, pattern.base_cost)

    def _add_artificial_overload(self, solver, objective, rows, phase):
        if self.cotwin.mode == "penalized" or phase == "feasibility":
            price = 1 if phase == "feasibility" else self.cotwin.hard_weight
            for fid, row in rows.items():
                slack = solver.NumVar(0, solver.infinity(), f"artificial_{fid}")
                row.SetCoefficient(slack, -1)
                objective.SetCoefficient(slack, price)
