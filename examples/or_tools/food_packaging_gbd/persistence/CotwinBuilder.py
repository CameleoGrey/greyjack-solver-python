"""Build the GBD line-route master in named mathematical groups."""

from copy import deepcopy
from datetime import datetime, timedelta
from itertools import combinations

from ortools.sat.python import cp_model

from ..cotwin.CotFoodPackaging import CotFoodPackaging, ModelFacts
from ..domain.PackagingSchedule import PackagingSchedule


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


class CotwinBuilder:
    def __init__(self, *, mode: str = "strict", use_greedy_hints: bool = True):
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode
        self.use_greedy_hints = use_greedy_hints

    def build_cotwin(self, domain: PackagingSchedule) -> CotFoodPackaging:
        domain.validate()
        snapshot = deepcopy(domain)
        facts = self._checked_facts(snapshot)
        model = cp_model.CpModel()
        assignment = self._add_assignments(model, snapshot)
        empty, arcs = self._add_line_routes(model, snapshot, assignment)
        before = (
            self._add_operator_orders(model, snapshot, assignment, arcs)
            if self.mode == "strict"
            else {}
        )
        hard, timing, cleaning = self._add_objective_terms(model, snapshot, facts, arcs)
        model.minimize(timing + cleaning if self.mode == "strict" else hard)
        error = model.validate()
        if error:
            raise ValueError(f"Invalid GBD master: {error}")
        return CotFoodPackaging(
            snapshot,
            facts,
            self.mode,
            model,
            assignment,
            empty,
            arcs,
            before,
            hard,
            timing,
            cleaning,
            self.use_greedy_hints,
        )

    def _checked_facts(self, domain: PackagingSchedule) -> ModelFacts:
        jobs, lines = domain.jobs, domain.lines
        if lines:
            origin = min(
                [line.start_date_time for line in lines]
                + [
                    stamp
                    for job in jobs
                    for stamp in (
                        job.min_start_time,
                        job.ideal_end_time,
                        job.max_end_time,
                    )
                ]
            )
        else:
            origin = datetime(2000, 1, 1)
        line_start = {
            line.id: _minutes(line.start_date_time - origin) for line in lines
        }
        duration = {job.id: _minutes(job.duration) for job in jobs}
        min_start = {job.id: _minutes(job.min_start_time - origin) for job in jobs}
        ideal_end = {job.id: _minutes(job.ideal_end_time - origin) for job in jobs}
        max_end = {job.id: _minutes(job.max_end_time - origin) for job in jobs}
        cleaning = {
            (incoming.id, previous.id): _minutes(
                incoming.product.get_cleanup_duration(previous.product)
            )
            for incoming in jobs
            for previous in jobs
            if incoming is not previous
        }
        max_cleaning = max(cleaning.values(), default=0)
        horizon = max([*line_start.values(), *min_start.values(), 0])
        horizon += sum(duration.values()) + max(0, len(jobs) - 1) * max_cleaning
        hard_bound = sum(max(0, horizon - max_end[j.id]) for j in jobs)
        medium_bound = len(lines) * horizon * horizon
        ideal_bound = sum(max(0, horizon - ideal_end[j.id]) for j in jobs)
        cleaning_bound = sum(j.priority * max_cleaning for j in jobs)
        overlap_bound = (
            sum(min(duration[a.id], duration[b.id]) for a, b in combinations(jobs, 2))
            if self.mode == "penalized"
            else 0
        )
        soft_bound = ideal_bound + cleaning_bound + overlap_bound
        medium_weight = soft_bound + 1
        safe = cp_model.INT_MAX // 2
        values = (
            horizon,
            horizon * horizon,
            hard_bound,
            medium_bound,
            ideal_bound,
            cleaning_bound,
            overlap_bound,
            soft_bound,
            medium_weight,
            medium_weight * medium_bound + soft_bound,
            2 * horizon + max(duration.values(), default=0) + max_cleaning,
            *(j.priority * max_cleaning for j in jobs),
        )
        if any(value > safe for value in values):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")
        return ModelFacts(
            origin,
            line_start,
            duration,
            min_start,
            ideal_end,
            max_end,
            cleaning,
            horizon,
            hard_bound,
            medium_bound,
            ideal_bound,
            cleaning_bound,
            overlap_bound,
            soft_bound,
            medium_weight,
        )

    @staticmethod
    def _add_assignments(model, domain):
        assignment = {
            (job.id, line.id): model.new_bool_var(f"assign_{job.id}_{line.id}")
            for job in domain.jobs
            for line in domain.lines
        }
        for job in domain.jobs:
            model.add_exactly_one(assignment[job.id, line.id] for line in domain.lines)
        return assignment

    @staticmethod
    def _add_line_routes(model, domain, assignment):
        empty = {}
        arcs = {}
        jobs = domain.jobs
        for line in domain.lines:
            lid = line.id
            empty[lid] = model.new_bool_var(f"empty_{lid}")
            circuit = [(0, 0, empty[lid])]
            for index, job in enumerate(jobs, 1):
                jid = job.id
                circuit.append((index, index, assignment[jid, lid].Not()))
                model.add_implication(assignment[jid, lid], empty[lid].Not())
                first = model.new_bool_var(f"first_{lid}_{jid}")
                last = model.new_bool_var(f"last_{lid}_{jid}")
                arcs[lid, None, jid] = first
                arcs[lid, jid, None] = last
                circuit.extend(((0, index, first), (index, 0, last)))
            for i, previous in enumerate(jobs, 1):
                for j, incoming in enumerate(jobs, 1):
                    if i == j:
                        continue
                    edge = model.new_bool_var(f"next_{lid}_{previous.id}_{incoming.id}")
                    arcs[lid, previous.id, incoming.id] = edge
                    circuit.append((i, j, edge))
            model.add_circuit(circuit)
        return empty, arcs

    @staticmethod
    def _add_operator_orders(model, domain, assignment, arcs):
        """Orient every shared-operator pair; ranks eliminate precedence cycles."""
        operators = sorted({line.operator for line in domain.lines})
        operator_lines = {
            name: [line.id for line in domain.lines if line.operator == name]
            for name in operators
        }
        ranks = {
            job.id: model.new_int_var(0, max(0, len(domain.jobs) - 1), f"rank_{job.id}")
            for job in domain.jobs
        }
        before = {}
        for left, right in combinations(domain.jobs, 2):
            a, b = left.id, right.id
            same_terms = []
            for name, lids in operator_lines.items():
                on_a = sum(assignment[a, lid] for lid in lids)
                on_b = sum(assignment[b, lid] for lid in lids)
                together = model.new_bool_var(f"both_{a}_{b}_{operators.index(name)}")
                model.add(together <= on_a)
                model.add(together <= on_b)
                model.add(together >= on_a + on_b - 1)
                same_terms.append(together)
            forward = model.new_bool_var(f"before_{a}_{b}")
            backward = model.new_bool_var(f"before_{b}_{a}")
            before[a, b], before[b, a] = forward, backward
            model.add(forward + backward == sum(same_terms))
            model.add(ranks[a] + 1 <= ranks[b]).only_enforce_if(forward)
            model.add(ranks[b] + 1 <= ranks[a]).only_enforce_if(backward)
        for (lid, previous, incoming), edge in arcs.items():
            if previous is not None and incoming is not None:
                model.add_implication(edge, before[previous, incoming])
        return before

    @staticmethod
    def _add_objective_terms(model, domain, facts, arcs):
        hard = model.new_int_var(0, facts.hard_bound, "hard_floor")
        timing_upper = (
            facts.medium_weight * facts.medium_bound
            + facts.ideal_bound
            + facts.overlap_bound
        )
        timing = model.new_int_var(0, timing_upper, "timing_floor")
        jobs = {job.id: job for job in domain.jobs}
        cleaning = sum(
            jobs[incoming].priority * facts.cleaning[incoming, previous] * edge
            for (lid, previous, incoming), edge in arcs.items()
            if previous is not None and incoming is not None
        )
        return hard, timing, cleaning
