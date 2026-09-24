from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import combinations

from ortools.sat.python import cp_model

from ..cotwin.CotFoodPackaging import CotFoodPackaging
from ..domain.PackagingSchedule import PackagingSchedule


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


@dataclass
class _ModelFacts:
    origin: datetime
    line_start: dict[int, int]
    duration: dict[int, int]
    min_start: dict[int, int]
    ideal_end: dict[int, int]
    max_end: dict[int, int]
    cleaning: dict[tuple[int, int], int]
    horizon: int
    hard_bound: int
    medium_bound: int
    ideal_bound: int
    cleaning_bound: int
    overlap_bound: int
    soft_bound: int
    medium_weight: int


@dataclass
class _ModelState:
    model: cp_model.CpModel
    start: dict[int, cp_model.IntVar] = field(default_factory=dict)
    end: dict[int, cp_model.IntVar] = field(default_factory=dict)
    late: dict[int, cp_model.IntVar] = field(default_factory=dict)
    ideal_late: dict[int, cp_model.IntVar] = field(default_factory=dict)
    assignment: dict[tuple[int, int], cp_model.IntVar] = field(default_factory=dict)
    empty_line: dict[int, cp_model.IntVar] = field(default_factory=dict)
    arcs: dict[tuple[int, int | None, int | None], cp_model.IntVar] = field(
        default_factory=dict
    )
    line_spans: dict[int, cp_model.IntVar] = field(default_factory=dict)
    span_squares: dict[int, cp_model.IntVar] = field(default_factory=dict)
    clean_terms: list = field(default_factory=list)
    operator_assignment: dict[tuple[int, int], cp_model.IntVar] = field(
        default_factory=dict
    )
    overlap_hints: dict = field(default_factory=dict)
    operator_overlap: cp_model.IntVar | None = None


class CotwinBuilder:
    def __init__(self, *, mode: str = "strict", use_greedy_hints: bool = True):
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode
        self.use_greedy_hints = use_greedy_hints

    def build_cotwin(self, domain: PackagingSchedule) -> CotFoodPackaging:
        domain.validate()
        facts = self._checked_model_facts(domain)
        state = _ModelState(cp_model.CpModel())
        self._add_job_times(state, facts, domain)
        self._add_line_assignments(state, domain)
        self._add_line_circuits(state, facts, domain)
        self._add_operator_rules(state, facts, domain)
        hard, medium, ideal, clean_penalty, soft = self._add_objective(state, facts)

        cotwin = CotFoodPackaging(
            state.model,
            facts.origin,
            self.mode,
            state.assignment,
            state.empty_line,
            state.arcs,
            state.start,
            state.end,
            hard,
            medium,
            soft,
            state.operator_overlap,
            ideal,
            clean_penalty,
            facts.medium_weight,
            facts.horizon,
            tuple(job.id for job in domain.jobs),
            tuple(line.id for line in domain.lines),
        )
        if self.use_greedy_hints:
            self._add_greedy_hints(domain, cotwin, facts, state)
        error = state.model.validate()
        if error:
            raise ValueError(f"Invalid CP-SAT model: {error}")
        return cotwin

    def _checked_model_facts(self, domain: PackagingSchedule) -> _ModelFacts:
        jobs = domain.jobs
        lines = domain.lines
        n = len(jobs)
        if lines:
            origin = min(
                [line.start_date_time for line in lines]
                + [
                    timestamp
                    for job in jobs
                    for timestamp in (
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
        horizon = (
            max([*line_start.values(), *min_start.values(), 0])
            + sum(duration.values())
            + max(0, n - 1) * max_cleaning
        )
        if not jobs:
            horizon = max([*line_start.values(), 0])
        hard_bound = sum(max(0, horizon - max_end[job.id]) for job in jobs)
        medium_bound = len(lines) * horizon * horizon
        ideal_bound = sum(max(0, horizon - ideal_end[job.id]) for job in jobs)
        cleaning_bound = sum(job.priority * max_cleaning for job in jobs)
        overlap_bound = (
            sum(
                min(duration[left.id], duration[right.id])
                for left, right in combinations(jobs, 2)
            )
            if self.mode == "penalized"
            else 0
        )
        soft_bound = ideal_bound + cleaning_bound + overlap_bound
        medium_weight = soft_bound + 1
        safe_bound = cp_model.INT_MAX // 2
        bounds = [
            horizon,
            horizon * horizon,
            hard_bound,
            medium_bound,
            soft_bound,
            medium_weight,
            medium_weight * medium_bound + soft_bound,
            max((job.priority for job in jobs), default=0) * max_cleaning,
        ]
        if any(value > safe_bound for value in bounds):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")
        return _ModelFacts(
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

    def _add_job_times(
        self, state: _ModelState, facts: _ModelFacts, domain: PackagingSchedule
    ) -> None:
        model = state.model
        for job in domain.jobs:
            jid = job.id
            state.start[jid] = model.new_int_var(0, facts.horizon, f"start_{jid}")
            state.end[jid] = model.new_int_var(0, facts.horizon, f"end_{jid}")
            model.add(state.end[jid] == state.start[jid] + facts.duration[jid])
            state.late[jid] = model.new_int_var(
                0, max(0, facts.horizon - facts.max_end[jid]), f"late_{jid}"
            )
            model.add_max_equality(
                state.late[jid], [0, state.end[jid] - facts.max_end[jid]]
            )
            state.ideal_late[jid] = model.new_int_var(
                0, max(0, facts.horizon - facts.ideal_end[jid]), f"ideal_late_{jid}"
            )
            model.add_max_equality(
                state.ideal_late[jid], [0, state.end[jid] - facts.ideal_end[jid]]
            )
            if self.mode == "strict":
                model.add(state.start[jid] >= facts.min_start[jid])
                model.add(state.end[jid] <= facts.max_end[jid])

    @staticmethod
    def _add_line_assignments(state: _ModelState, domain: PackagingSchedule) -> None:
        state.assignment = {
            (job.id, line.id): state.model.new_bool_var(f"assign_{job.id}_{line.id}")
            for job in domain.jobs
            for line in domain.lines
        }
        for job in domain.jobs:
            state.model.add_exactly_one(
                state.assignment[job.id, line.id] for line in domain.lines
            )

    @staticmethod
    def _add_line_circuits(
        state: _ModelState, facts: _ModelFacts, domain: PackagingSchedule
    ) -> None:
        model = state.model
        jobs = domain.jobs
        for line in domain.lines:
            lid = line.id
            empty = model.new_bool_var(f"empty_{lid}")
            state.empty_line[lid] = empty
            span = model.new_int_var(0, facts.horizon, f"span_{lid}")
            square = model.new_int_var(
                0, facts.horizon * facts.horizon, f"span_square_{lid}"
            )
            state.line_spans[lid] = span
            state.span_squares[lid] = square
            model.add_multiplication_equality(square, [span, span])
            model.add(span == 0).only_enforce_if(empty)
            if not jobs:
                model.add(empty == 1)
                continue

            # A circuit orders exactly the jobs assigned to this line.
            circuit = [(0, 0, empty)]
            for index, job in enumerate(jobs, start=1):
                jid = job.id
                circuit.append((index, index, state.assignment[jid, lid].Not()))
                first = model.new_bool_var(f"first_{lid}_{jid}")
                last = model.new_bool_var(f"last_{lid}_{jid}")
                state.arcs[lid, None, jid] = first
                state.arcs[lid, jid, None] = last
                circuit.extend(((0, index, first), (index, 0, last)))
                model.add(state.start[jid] >= facts.line_start[lid]).only_enforce_if(
                    first
                )
                model.add(
                    span == state.end[jid] - facts.line_start[lid]
                ).only_enforce_if(last)
            for previous_index, previous in enumerate(jobs, start=1):
                for incoming_index, incoming in enumerate(jobs, start=1):
                    if previous_index == incoming_index:
                        continue
                    edge = model.new_bool_var(f"next_{lid}_{previous.id}_{incoming.id}")
                    state.arcs[lid, previous.id, incoming.id] = edge
                    circuit.append((previous_index, incoming_index, edge))
                    model.add(
                        state.start[incoming.id]
                        >= state.end[previous.id]
                        + facts.cleaning[incoming.id, previous.id]
                    ).only_enforce_if(edge)
                    state.clean_terms.append(
                        incoming.priority
                        * facts.cleaning[incoming.id, previous.id]
                        * edge
                    )
            model.add_circuit(circuit)

    def _add_operator_rules(
        self, state: _ModelState, facts: _ModelFacts, domain: PackagingSchedule
    ) -> None:
        model = state.model
        jobs = domain.jobs
        lines = domain.lines
        operator_ids = sorted({line.operator for line in lines})
        for job in jobs:
            for operator in operator_ids:
                selected = model.new_bool_var(f"operator_{job.id}_{operator}")
                relevant_lines = [
                    state.assignment[job.id, line.id]
                    for line in lines
                    if line.operator == operator
                ]
                model.add_max_equality(selected, relevant_lines)
                state.operator_assignment[job.id, operator] = selected
        if self.mode == "strict":
            for operator in operator_ids:
                intervals = [
                    model.new_optional_interval_var(
                        state.start[job.id],
                        facts.duration[job.id],
                        state.end[job.id],
                        state.operator_assignment[job.id, operator],
                        f"production_{job.id}_{operator}",
                    )
                    for job in jobs
                ]
                model.add_no_overlap(intervals)
            state.operator_overlap = model.new_int_var(0, 0, "operator_overlap")
        else:
            overlap_terms = []
            for left, right in combinations(jobs, 2):
                pair = left.id, right.id
                both = []
                for operator in operator_ids:
                    shared = model.new_bool_var(f"both_{left.id}_{right.id}_{operator}")
                    first = state.operator_assignment[left.id, operator]
                    second = state.operator_assignment[right.id, operator]
                    model.add(shared <= first)
                    model.add(shared <= second)
                    model.add(shared >= first + second - 1)
                    both.append(shared)
                    state.overlap_hints[pair, "both", operator] = shared
                same = model.new_bool_var(f"same_operator_{left.id}_{right.id}")
                model.add(same == sum(both))
                min_end = model.new_int_var(
                    0, facts.horizon, f"min_end_{left.id}_{right.id}"
                )
                max_start = model.new_int_var(
                    0, facts.horizon, f"max_start_{left.id}_{right.id}"
                )
                model.add_min_equality(
                    min_end, [state.end[left.id], state.end[right.id]]
                )
                model.add_max_equality(
                    max_start, [state.start[left.id], state.start[right.id]]
                )
                overlap = model.new_int_var(
                    0,
                    min(facts.duration[left.id], facts.duration[right.id]),
                    f"overlap_{left.id}_{right.id}",
                )
                model.add_max_equality(overlap, [0, min_end - max_start])
                contribution = model.new_int_var(
                    0,
                    min(facts.duration[left.id], facts.duration[right.id]),
                    f"operator_overlap_{left.id}_{right.id}",
                )
                model.add(contribution == overlap).only_enforce_if(same)
                model.add(contribution == 0).only_enforce_if(same.Not())
                overlap_terms.append(contribution)
                state.overlap_hints[pair] = (
                    same,
                    min_end,
                    max_start,
                    overlap,
                    contribution,
                )
            state.operator_overlap = model.new_int_var(
                0, facts.overlap_bound, "operator_overlap"
            )
            model.add(state.operator_overlap == sum(overlap_terms))

    def _add_objective(
        self, state: _ModelState, facts: _ModelFacts
    ) -> tuple[
        cp_model.IntVar,
        cp_model.IntVar,
        cp_model.IntVar,
        cp_model.IntVar,
        cp_model.IntVar,
    ]:
        model = state.model
        hard = model.new_int_var(0, facts.hard_bound, "hard_penalty")
        medium = model.new_int_var(0, facts.medium_bound, "medium_penalty")
        ideal = model.new_int_var(0, facts.ideal_bound, "ideal_lateness")
        clean_penalty = model.new_int_var(0, facts.cleaning_bound, "cleaning_penalty")
        soft = model.new_int_var(0, facts.soft_bound, "soft_penalty")
        model.add(hard == sum(state.late.values()))
        model.add(medium == sum(state.span_squares.values()))
        model.add(ideal == sum(state.ideal_late.values()))
        model.add(clean_penalty == sum(state.clean_terms))
        model.add(soft == ideal + clean_penalty + state.operator_overlap)
        if self.mode == "strict":
            model.add(hard == 0)
            model.minimize(facts.medium_weight * medium + soft)
        else:
            # The solver fixes the proven minimum hard score before optimizing
            # medium and soft penalties in its second phase.
            model.minimize(hard)
        return hard, medium, ideal, clean_penalty, soft

    def _add_greedy_hints(
        self,
        domain: PackagingSchedule,
        cotwin: CotFoodPackaging,
        facts: _ModelFacts,
        state: _ModelState,
    ) -> None:
        duration = facts.duration
        line_start = facts.line_start
        min_start = facts.min_start
        max_end = facts.max_end
        ideal_end = facts.ideal_end
        cleaning = facts.cleaning
        late = state.late
        ideal_late = state.ideal_late
        line_spans = state.line_spans
        span_squares = state.span_squares
        operator_assignment = state.operator_assignment
        overlap_hints = state.overlap_hints
        lines = domain.lines
        jobs = domain.jobs
        routes = {line.id: [] for line in lines}
        line_end = dict(line_start)
        operator_end = {
            operator: min(
                line_start[line.id] for line in lines if line.operator == operator
            )
            for operator in {line.operator for line in lines}
        }
        start_values = {}
        end_values = {}
        for job in sorted(
            jobs, key=lambda item: (item.max_end_time, item.ideal_end_time, item.id)
        ):
            choices = []
            for line in lines:
                previous = routes[line.id][-1] if routes[line.id] else None
                cleanup = cleaning[job.id, previous] if previous is not None else 0
                candidate = line_end[line.id] + cleanup
                if self.mode == "strict":
                    candidate = max(
                        candidate, min_start[job.id], operator_end[line.operator]
                    )
                completion = candidate + duration[job.id]
                choices.append(
                    (
                        max(0, completion - max_end[job.id]),
                        completion,
                        line.id,
                        candidate,
                    )
                )
            _, completion, lid, candidate = min(choices)
            if self.mode == "strict" and completion > max_end[job.id]:
                return
            routes[lid].append(job.id)
            start_values[job.id] = candidate
            end_values[job.id] = completion
            line_end[lid] = completion
            if self.mode == "strict":
                operator = next(line.operator for line in lines if line.id == lid)
                operator_end[operator] = completion

        selected_edges = set()
        for line in lines:
            route = routes[line.id]
            if route:
                selected_edges.add((line.id, None, route[0]))
                selected_edges.add((line.id, route[-1], None))
                selected_edges.update(
                    (line.id, left, right) for left, right in zip(route, route[1:])
                )
            cotwin.model.add_hint(cotwin.empty_line[line.id], int(not route))
            span = end_values[route[-1]] - line_start[line.id] if route else 0
            cotwin.model.add_hint(line_spans[line.id], span)
            cotwin.model.add_hint(span_squares[line.id], span * span)
        for key, variable in cotwin.assignment.items():
            jid, lid = key
            cotwin.model.add_hint(variable, int(jid in routes[lid]))
        for key, variable in cotwin.arcs.items():
            cotwin.model.add_hint(variable, int(key in selected_edges))
        operators = {line.id: line.operator for line in lines}
        job_operator = {
            jid: operators[lid] for lid, route in routes.items() for jid in route
        }
        for key, variable in operator_assignment.items():
            cotwin.model.add_hint(variable, int(job_operator[key[0]] == key[1]))
        for job in jobs:
            jid = job.id
            cotwin.model.add_hint(cotwin.start[jid], start_values[jid])
            cotwin.model.add_hint(cotwin.end[jid], end_values[jid])
            cotwin.model.add_hint(late[jid], max(0, end_values[jid] - max_end[jid]))
            cotwin.model.add_hint(
                ideal_late[jid], max(0, end_values[jid] - ideal_end[jid])
            )
        overlap_total = 0
        if self.mode == "penalized":
            for left, right in combinations(jobs, 2):
                pair = left.id, right.id
                same = job_operator[left.id] == job_operator[right.id]
                low_end = min(end_values[left.id], end_values[right.id])
                high_start = max(start_values[left.id], start_values[right.id])
                overlap = max(0, low_end - high_start)
                contribution = overlap if same else 0
                overlap_total += contribution
                variables = overlap_hints[pair]
                for variable, value in zip(
                    variables, (same, low_end, high_start, overlap, contribution)
                ):
                    cotwin.model.add_hint(variable, int(value))
                for operator in {line.operator for line in lines}:
                    cotwin.model.add_hint(
                        overlap_hints[pair, "both", operator],
                        int(
                            job_operator[left.id] == job_operator[right.id] == operator
                        ),
                    )
        clean_total = sum(
            next(job.priority for job in jobs if job.id == jid)
            * cleaning[jid, previous]
            for route in routes.values()
            for previous, jid in zip(route, route[1:])
        )
        ideal_total = sum(
            max(0, end_values[job.id] - ideal_end[job.id]) for job in jobs
        )
        hard_total = sum(max(0, end_values[job.id] - max_end[job.id]) for job in jobs)
        medium_total = sum(
            (end_values[route[-1]] - line_start[lid]) ** 2 if route else 0
            for lid, route in routes.items()
        )
        cotwin.model.add_hint(cotwin.hard_penalty, hard_total)
        cotwin.model.add_hint(cotwin.medium_penalty, medium_total)
        cotwin.model.add_hint(cotwin.ideal_lateness, ideal_total)
        cotwin.model.add_hint(cotwin.cleaning_penalty, clean_total)
        cotwin.model.add_hint(cotwin.operator_overlap, overlap_total)
        cotwin.model.add_hint(
            cotwin.soft_penalty, ideal_total + clean_total + overlap_total
        )
