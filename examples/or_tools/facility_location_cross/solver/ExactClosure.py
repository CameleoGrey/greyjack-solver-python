"""Full CP-SAT model used to close an integer gap or prove infeasibility."""

from dataclasses import dataclass
from typing import Callable

from ortools.sat.python import cp_model

from ..cotwin import CotFacilityLocation


@dataclass
class ExactModel:
    model: cp_model.CpModel
    assignments: dict[int, dict[int, cp_model.IntVar]]
    used: dict[int, cp_model.IntVar]
    hard: cp_model.IntVar
    soft: cp_model.IntVar


class _ClosureCallback(cp_model.CpSolverSolutionCallback):
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


class ExactClosure:
    def __init__(self, cotwin: CotFacilityLocation):
        self.cotwin = cotwin

    def solve(
        self,
        seconds: float,
        workers: int,
        on_assignment: Callable[[dict[int, int]], None],
        *,
        hint: dict[int, int] | None = None,
        cutoff: int | None = None,
    ) -> tuple[int, dict[int, int] | None]:
        built = self.build_model(hint=hint, cutoff=cutoff)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = max(0.001, seconds)
        callback = _ClosureCallback(
            built.assignments,
            tuple(c.id for c in self.cotwin.domain.consumers),
            on_assignment,
        )
        status = solver.solve(built.model, callback)
        if status == cp_model.MODEL_INVALID:
            raise ValueError(f"Invalid exact-closure model: {built.model.validate()}")
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return status, None
        assignment = {
            cid: next(fid for fid, var in row.items() if solver.value(var))
            for cid, row in built.assignments.items()
        }
        return status, assignment

    def build_model(
        self, *, hint: dict[int, int] | None = None, cutoff: int | None = None
    ) -> ExactModel:
        model = cp_model.CpModel()
        assignments = self._add_customer_assignment(model)
        used = self._add_exact_usage(model, assignments)
        overloads = self._add_capacity(model, assignments)
        hard, soft = self._add_score_and_objective(model, assignments, used, overloads)
        if cutoff is not None:
            model.add(self.cotwin.hard_weight * hard + soft <= cutoff)
        if hint is not None and cutoff is None:
            self._add_hint(model, assignments, used, hint)
        error = model.validate()
        if error:
            raise ValueError(f"Invalid exact-closure model: {error}")
        return ExactModel(model, assignments, used, hard, soft)

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

    def _add_capacity(self, model, assignments):
        total_demand = sum(c.demand for c in self.cotwin.domain.consumers)
        overloads = {}
        for facility in self.cotwin.domain.facilities:
            load = sum(
                c.demand * assignments[c.id][facility.id]
                for c in self.cotwin.domain.consumers
            )
            if self.cotwin.mode == "strict":
                model.add(load <= facility.capacity)
            else:
                excess = model.new_int_var(
                    0,
                    max(0, total_demand - facility.capacity),
                    f"overload_{facility.id}",
                )
                model.add_max_equality(excess, [0, load - facility.capacity])
                overloads[facility.id] = excess
        return overloads

    def _add_score_and_objective(self, model, assignments, used, overloads):
        total_demand = sum(c.demand for c in self.cotwin.domain.consumers)
        hard = model.new_int_var(0, total_demand, "hard_penalty")
        model.add(hard == sum(overloads.values()))
        distance_upper = (
            self.cotwin.assignment_upper - self.cotwin.hard_weight * total_demand
        )
        soft = model.new_int_var(
            self.cotwin.setup_lower,
            self.cotwin.setup_upper + distance_upper,
            "soft_cost",
        )
        model.add(
            soft
            == sum(2 * f.setup_cost * used[f.id] for f in self.cotwin.domain.facilities)
            + sum(
                5 * self.cotwin.distances[c.id, f.id] * assignments[c.id][f.id]
                for c in self.cotwin.domain.consumers
                for f in self.cotwin.domain.facilities
            )
        )
        model.minimize(self.cotwin.hard_weight * hard + soft)
        return hard, soft

    def _add_hint(self, model, assignments, used, hint):
        if set(hint) != set(assignments):
            raise ValueError("Incomplete exact-closure hint")
        for cid, row in assignments.items():
            for fid, variable in row.items():
                model.add_hint(variable, int(hint[cid] == fid))
        active = set(hint.values())
        for fid, variable in used.items():
            model.add_hint(variable, int(fid in active))
