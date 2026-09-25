"""Build the assignment and activation groups of the Lagrangian cotwin."""

from collections import defaultdict
from copy import deepcopy

from ortools.linear_solver import pywraplp

from ..cotwin.CotScheduleCB import CotScheduleCB, DemandGroup
from ..domain.ScheduleCB import ScheduleCB


class CotwinBuilder:
    def __init__(self, *, mode: str = "penalized", use_greedy_seed: bool = True):
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode
        self.use_greedy_seed = use_greedy_seed

    def build_cotwin(self, domain: ScheduleCB) -> CotScheduleCB:
        domain.validate()
        snapshot = deepcopy(domain)
        self._check_numeric_bounds(snapshot)
        model = pywraplp.Solver.CreateSolver("GLOP")
        if model is None:
            raise RuntimeError("OR-Tools GLOP is unavailable")
        groups = self._add_assignment_groups(model, snapshot)
        activation = self._add_activation_choices(model, snapshot)
        # Resource and activation links are relaxed into objective coefficients
        # by the solver. Only the independent choice constraints remain here.
        model.Objective().SetMinimization()
        return CotScheduleCB(
            snapshot,
            model,
            groups,
            activation,
            self.mode,
            sum(computer.cost for computer in snapshot.computers) + 1,
            self.use_greedy_seed,
        )

    def _check_numeric_bounds(self, domain: ScheduleCB) -> None:
        # Retain the source example's safe integer-score range. GLOP may round
        # coefficients, but accepted business scores and dual checks use exact
        # integers and decimals independently of its objective value.
        safe_bound = (1 << 62) - 1
        totals = tuple(
            sum(p.requirements[r] for p in domain.processes) for r in range(3)
        )
        hard_upper = sum(totals)
        cost_upper = sum(c.cost for c in domain.computers)
        values = [
            *totals,
            hard_upper,
            cost_upper,
            *(resource for c in domain.computers for resource in c.resources),
        ]
        if self.mode == "penalized":
            values.extend((cost_upper + 1, (cost_upper + 1) * hard_upper + cost_upper))
        if any(value > safe_bound for value in values):
            raise ValueError("Dataset exceeds safe GLOP numeric bounds")

    @staticmethod
    def _add_assignment_groups(
        model: pywraplp.Solver, domain: ScheduleCB
    ) -> tuple[DemandGroup, ...]:
        by_requirements: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        for process in domain.processes:
            by_requirements[process.requirements].append(process.process_id)

        groups = []
        for index, (requirements, process_ids) in enumerate(by_requirements.items()):
            count = len(process_ids)
            choices = {
                c.computer_id: model.NumVar(
                    0, count, f"assigned_{index}_{c.computer_id}"
                )
                for c in domain.computers
            }
            exactly_count = model.RowConstraint(count, count, f"place_group_{index}")
            for variable in choices.values():
                exactly_count.SetCoefficient(variable, 1)
            groups.append(DemandGroup(requirements, tuple(process_ids), choices))
        return tuple(groups)

    @staticmethod
    def _add_activation_choices(
        model: pywraplp.Solver, domain: ScheduleCB
    ) -> dict[int, pywraplp.Variable]:
        return {
            c.computer_id: model.NumVar(0, 1, f"used_{c.computer_id}")
            for c in domain.computers
        }
