from ortools.sat.python import cp_model

from ..cotwin.CotScheduleCB import CotScheduleCB
from ..domain.ScheduleCB import ScheduleCB


class CotwinBuilder:
    def __init__(self, use_greed_init: bool = True, *, mode: str = "penalized"):
        if mode not in ("penalized", "strict"):
            raise ValueError("mode must be 'penalized' or 'strict'")
        self.use_greed_init = use_greed_init
        self.mode = mode

    def build_cotwin(self, domain: ScheduleCB) -> CotScheduleCB:
        domain.validate()
        totals, cost_bound, hard_bound, hard_weight = self._checked_score_bounds(domain)
        model = cp_model.CpModel()
        assignments = self._add_assignments(model, domain)
        used, overloads = self._add_resource_constraints(
            model, domain, assignments, totals
        )
        hard_penalty, soft_cost = self._add_objective(
            model, domain, used, overloads, cost_bound, hard_bound, hard_weight
        )

        cotwin = CotScheduleCB(
            model,
            assignments,
            used,
            overloads,
            hard_penalty,
            soft_cost,
            hard_weight,
            self.mode,
        )
        if self.use_greed_init:
            self._add_greedy_hints(domain, cotwin)
        validation_error = model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        return cotwin

    def _checked_score_bounds(
        self, domain: ScheduleCB
    ) -> tuple[tuple[int, ...], int, int, int]:
        totals = tuple(
            sum(p.requirements[r] for p in domain.processes) for r in range(3)
        )
        cost_bound = sum(c.cost for c in domain.computers)
        hard_bound = sum(totals)
        hard_weight = cost_bound + 1 if self.mode == "penalized" else 0
        # CP-SAT reserves part of the int64 range for safe internal arithmetic.
        safe_bound = cp_model.INT_MAX // 2
        values = [*totals, cost_bound, hard_bound]
        if self.mode == "penalized":
            values.extend((hard_weight, hard_bound * hard_weight + cost_bound))
        values.extend(value for c in domain.computers for value in c.resources)
        if any(value > safe_bound for value in values):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")
        return totals, cost_bound, hard_bound, hard_weight

    @staticmethod
    def _add_assignments(
        model: cp_model.CpModel, domain: ScheduleCB
    ) -> dict[int, dict[int, cp_model.IntVar]]:
        assignments = {}
        for process in domain.processes:
            row = {
                c.computer_id: model.new_bool_var(
                    f"assign_{process.process_id}_{c.computer_id}"
                )
                for c in domain.computers
            }
            model.add_exactly_one(row.values())
            assignments[process.process_id] = row
        return assignments

    def _add_resource_constraints(
        self,
        model: cp_model.CpModel,
        domain: ScheduleCB,
        assignments: dict[int, dict[int, cp_model.IntVar]],
        totals: tuple[int, ...],
    ) -> tuple[dict[int, cp_model.IntVar], dict[int, tuple[cp_model.IntVar, ...]]]:
        used = {}
        overloads = {}
        for computer in domain.computers:
            cid = computer.computer_id
            column = [assignments[p.process_id][cid] for p in domain.processes]
            used[cid] = model.new_bool_var(f"used_{cid}")
            if column:
                model.add_max_equality(used[cid], column)
            else:
                model.add(used[cid] == 0)
            excess_vars = []
            for r, capacity in enumerate(computer.resources):
                consumption = cp_model.LinearExpr.weighted_sum(
                    column, [p.requirements[r] for p in domain.processes]
                )
                if self.mode == "strict":
                    model.add(consumption <= capacity)
                # Penalized mode records the same capacity violation as a hard score.
                excess = model.new_int_var(
                    0, max(0, totals[r] - capacity), f"overload_{cid}_{r}"
                )
                model.add_max_equality(excess, [0, consumption - capacity])
                excess_vars.append(excess)
            overloads[cid] = tuple(excess_vars)
        return used, overloads

    def _add_objective(
        self,
        model: cp_model.CpModel,
        domain: ScheduleCB,
        used: dict[int, cp_model.IntVar],
        overloads: dict[int, tuple[cp_model.IntVar, ...]],
        cost_bound: int,
        hard_bound: int,
        hard_weight: int,
    ) -> tuple[cp_model.IntVar, cp_model.IntVar]:
        hard_penalty = model.new_int_var(0, hard_bound, "hard_penalty")
        soft_cost = model.new_int_var(0, cost_bound, "soft_cost")
        model.add(hard_penalty == sum(v for row in overloads.values() for v in row))
        model.add(
            soft_cost == sum(c.cost * used[c.computer_id] for c in domain.computers)
        )
        if self.mode == "strict":
            model.add(hard_penalty == 0)
            model.minimize(soft_cost)
        else:
            # One overload point outweighs every possible change in running cost.
            model.minimize(hard_weight * hard_penalty + soft_cost)
        return hard_penalty, soft_cost

    @staticmethod
    def _add_greedy_hints(domain: ScheduleCB, cotwin: CotScheduleCB) -> None:
        """Hint the original first-fit placement; leave unplaceable processes free."""
        loads = {c.computer_id: [0, 0, 0] for c in domain.computers}
        chosen = {}
        for process in domain.processes:
            for computer in domain.computers:
                cid = computer.computer_id
                if all(
                    loads[cid][r] + process.requirements[r] <= computer.resources[r]
                    for r in range(3)
                ):
                    chosen[process.process_id] = cid
                    for r, demand in enumerate(process.requirements):
                        loads[cid][r] += demand
                    break
        for pid, cid in chosen.items():
            for candidate, variable in cotwin.assignment_variables[pid].items():
                cotwin.model.add_hint(variable, int(candidate == cid))

        # Complete hints include auxiliaries, so CP-SAT can recognize the incumbent.
        if len(chosen) == len(domain.processes):
            active = set(chosen.values())
            for cid, variable in cotwin.computer_used.items():
                cotwin.model.add_hint(variable, int(cid in active))
            for row in cotwin.resource_overloads.values():
                for variable in row:
                    cotwin.model.add_hint(variable, 0)
            cotwin.model.add_hint(cotwin.hard_penalty, 0)
            cotwin.model.add_hint(
                cotwin.soft_cost,
                sum(c.cost for c in domain.computers if c.computer_id in active),
            )
