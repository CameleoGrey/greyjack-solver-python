"""Exact fixed-route timing and certified convex GBD cuts."""

from dataclasses import dataclass
from datetime import timedelta
from fractions import Fraction
from itertools import combinations
from math import floor, isfinite

from ortools.math_opt.python import mathopt
from ortools.sat.python import cp_model

from ..cotwin.CotFoodPackaging import CotFoodPackaging


@dataclass(frozen=True)
class TimingResult:
    feasible: bool
    starts: dict[int, int] | None
    hard: int | None
    medium: int | None
    ideal: int | None
    overlap: int | None


def earliest_schedule(cotwin: CotFoodPackaging, routes, before=()) -> TimingResult:
    """Solve fixed precedence exactly by longest paths on integer minutes."""
    facts = cotwin.facts
    starts = {
        jid: (facts.min_start[jid] if cotwin.mode == "strict" else 0)
        for jid in cotwin.job_ids
    }
    edges = []
    for lid, route in routes.items():
        if route:
            starts[route[0]] = max(starts[route[0]], facts.line_start[lid])
        for previous, incoming in zip(route, route[1:]):
            edges.append(
                (
                    previous,
                    incoming,
                    facts.duration[previous] + facts.cleaning[incoming, previous],
                )
            )
    if cotwin.mode == "strict":
        edges.extend((a, b, facts.duration[a]) for a, b in before)
    for _ in range(len(starts)):
        changed = False
        for a, b, lag in edges:
            candidate = starts[a] + lag
            if candidate > starts[b]:
                starts[b] = candidate
                changed = True
        if not changed:
            break
    else:
        if any(starts[a] + lag > starts[b] for a, b, lag in edges):
            return TimingResult(False, None, None, None, None, None)
    if any(starts[j] > facts.horizon - facts.duration[j] for j in starts):
        return TimingResult(False, None, None, None, None, None)
    if cotwin.mode == "strict" and any(
        starts[j] + facts.duration[j] > facts.max_end[j] for j in starts
    ):
        return TimingResult(False, None, None, None, None, None)
    ends = {j: starts[j] + facts.duration[j] for j in starts}
    hard = sum(max(0, ends[j] - facts.max_end[j]) for j in starts)
    ideal = sum(max(0, ends[j] - facts.ideal_end[j]) for j in starts)
    medium = sum(
        (ends[route[-1]] - facts.line_start[lid]) ** 2 if route else 0
        for lid, route in routes.items()
    )
    operator = {
        j: line.operator for line in cotwin.domain.lines for j in routes[line.id]
    }
    overlap = sum(
        max(0, min(ends[a], ends[b]) - max(starts[a], starts[b]))
        for a, b in combinations(starts, 2)
        if operator[a] == operator[b]
    )
    return TimingResult(True, starts, hard, medium, ideal, overlap)


class _TimingCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, routes, starts, record):
        super().__init__()
        self.routes = routes
        self.starts = starts
        self.record = record

    def on_solution_callback(self):
        self.record(self.routes, {j: self.value(v) for j, v in self.starts.items()})


def _add_integer_job_times(model, cotwin, hard_optimum):
    facts = cotwin.facts
    starts = {
        j: model.new_int_var(0, facts.horizon, f"start_{j}") for j in cotwin.job_ids
    }
    ends = {j: model.new_int_var(0, facts.horizon, f"end_{j}") for j in cotwin.job_ids}
    late = {}
    ideal = {}
    for j in cotwin.job_ids:
        model.add(ends[j] == starts[j] + facts.duration[j])
        late[j] = model.new_int_var(
            0, max(0, facts.horizon - facts.max_end[j]), f"late_{j}"
        )
        ideal[j] = model.new_int_var(
            0, max(0, facts.horizon - facts.ideal_end[j]), f"ideal_{j}"
        )
        model.add_max_equality(late[j], [0, ends[j] - facts.max_end[j]])
        model.add_max_equality(ideal[j], [0, ends[j] - facts.ideal_end[j]])
    model.add(sum(late.values()) == hard_optimum)
    return starts, ends, ideal


def _add_integer_line_routes(model, cotwin, routes, starts, ends):
    facts = cotwin.facts
    squares = []
    for lid, route in routes.items():
        if not route:
            continue
        model.add(starts[route[0]] >= facts.line_start[lid])
        for a, b in zip(route, route[1:]):
            model.add(starts[b] >= ends[a] + facts.cleaning[b, a])
        span = model.new_int_var(0, facts.horizon, f"span_{lid}")
        square = model.new_int_var(0, facts.horizon * facts.horizon, f"square_{lid}")
        model.add(span == ends[route[-1]] - facts.line_start[lid])
        model.add_multiplication_equality(square, [span, span])
        squares.append(square)
    return squares


def _add_integer_operator_overlap(model, cotwin, routes, starts, ends):
    facts = cotwin.facts
    operator = {
        j: line.operator for line in cotwin.domain.lines for j in routes[line.id]
    }
    overlaps = []
    for a, b in combinations(cotwin.job_ids, 2):
        if operator[a] != operator[b]:
            continue
        min_end = model.new_int_var(0, facts.horizon, f"min_end_{a}_{b}")
        max_start = model.new_int_var(0, facts.horizon, f"max_start_{a}_{b}")
        overlap = model.new_int_var(
            0, min(facts.duration[a], facts.duration[b]), f"overlap_{a}_{b}"
        )
        model.add_min_equality(min_end, [ends[a], ends[b]])
        model.add_max_equality(max_start, [starts[a], starts[b]])
        model.add_max_equality(overlap, [0, min_end - max_start])
        overlaps.append(overlap)
    return overlaps


def solve_integer_timing(
    cotwin: CotFoodPackaging,
    routes,
    hard_optimum: int,
    seconds: float,
    record,
    activate,
    deactivate,
    workers: int,
) -> tuple[int, int | None]:
    """Resolve the penalized pairwise-overlap score for one route pattern."""
    facts = cotwin.facts
    model = cp_model.CpModel()
    starts, ends, ideal = _add_integer_job_times(model, cotwin, hard_optimum)
    squares = _add_integer_line_routes(model, cotwin, routes, starts, ends)
    overlap_terms = _add_integer_operator_overlap(model, cotwin, routes, starts, ends)
    model.minimize(
        facts.medium_weight * sum(squares) + sum(ideal.values()) + sum(overlap_terms)
    )
    error = model.validate()
    if error:
        raise ValueError(f"Invalid timing subproblem: {error}")
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = max(0.001, seconds)
    callback = _TimingCallback(routes, starts, record)
    activate(solver)
    try:
        status = solver.solve(model, callback)
    finally:
        deactivate(solver)
    cost = (
        facts.medium_weight * sum(solver.value(square) for square in squares)
        + sum(solver.value(value) for value in ideal.values())
        + sum(solver.value(value) for value in overlap_terms)
        if status == cp_model.OPTIMAL
        else None
    )
    return status, cost


@dataclass(frozen=True)
class _Row:
    values: dict[str, int]
    base: int
    binary: dict[int, int]


def convex_cut(
    cotwin: CotFoodPackaging, selected: set[int], phase: str, seconds: float
):
    """Return an integer affine lower bound from a rationalized QP dual.

    Every nonnegative multiplier is dual feasible after box minimization. Thus
    numerical PDLP output only chooses a multiplier; it never certifies the cut.
    """
    f = cotwin.facts
    if seconds <= 0.001:
        return None
    strict = cotwin.mode == "strict"
    bounds = {}
    q = {}
    c = {}
    for j in cotwin.job_ids:
        lb = f.min_start[j] if strict else 0
        ub = (
            min(f.horizon - f.duration[j], f.max_end[j] - f.duration[j])
            if strict
            else f.horizon - f.duration[j]
        )
        if lb > ub:
            return None
        bounds[f"s{j}"] = (lb, ub)
        if phase == "hard":
            bounds[f"h{j}"] = (0, max(0, f.horizon - f.max_end[j]))
            c[f"h{j}"] = 1
        else:
            bounds[f"i{j}"] = (0, max(0, f.horizon - f.ideal_end[j]))
            c[f"i{j}"] = 1
    if phase != "hard":
        for lid in cotwin.line_ids:
            bounds[f"t{lid}"] = (0, f.horizon)
            q[f"t{lid}"] = f.medium_weight
    big = (
        2 * f.horizon
        + max(f.duration.values(), default=0)
        + max(f.cleaning.values(), default=0)
    )
    rows = []
    for (lid, a, b), binary in cotwin.arcs.items():
        # Inactive big-M rows are redundant at this pattern. Their multiplier
        # may be zero in a globally valid Lagrangian cut.
        if binary.index not in selected:
            continue
        if a is None:
            rows.append(
                _Row({f"s{b}": 1}, f.line_start[lid] - big, {binary.index: big})
            )
        elif b is None:
            if phase != "hard":
                rows.append(
                    _Row(
                        {f"t{lid}": 1, f"s{a}": -1},
                        f.duration[a] - f.line_start[lid] - big,
                        {binary.index: big},
                    )
                )
        else:
            rows.append(
                _Row(
                    {f"s{b}": 1, f"s{a}": -1},
                    f.duration[a] + f.cleaning[b, a] - big,
                    {binary.index: big},
                )
            )
    if strict:
        for (a, b), binary in cotwin.operator_before.items():
            if binary.index not in selected:
                continue
            rows.append(
                _Row(
                    {f"s{b}": 1, f"s{a}": -1}, f.duration[a] - big, {binary.index: big}
                )
            )
    for j in cotwin.job_ids:
        if phase == "hard":
            rows.append(
                _Row({f"h{j}": 1, f"s{j}": -1}, f.duration[j] - f.max_end[j], {})
            )
        else:
            rows.append(
                _Row({f"i{j}": 1, f"s{j}": -1}, f.duration[j] - f.ideal_end[j], {})
            )
    model = mathopt.Model()
    variables = {
        name: model.add_variable(lb=lb, ub=ub, name=name)
        for name, (lb, ub) in bounds.items()
    }
    constraints = []
    for row in rows:
        rhs = row.base + sum(
            value for index, value in row.binary.items() if index in selected
        )
        constraints.append(
            model.add_linear_constraint(
                sum(value * variables[name] for name, value in row.values.items())
                >= rhs
            )
        )
    model.minimize(
        sum(value * variables[name] for name, value in c.items())
        + sum(value * variables[name] * variables[name] for name, value in q.items())
    )
    try:
        result = mathopt.solve(
            model,
            mathopt.SolverType.PDLP,
            params=mathopt.SolveParameters(time_limit=timedelta(seconds=seconds)),
        )
        # A timed-out PDLP run may still expose multipliers with undetermined
        # numerical status. They are only proposals: the exact box minimum
        # below certifies the cut after nonnegative rational conversion.
        dual = next(
            (
                solution.dual_solution
                for solution in result.solutions
                if solution.dual_solution is not None
            ),
            None,
        )
        if dual is None:
            return None
        duals = dual.dual_values
    except (RuntimeError, ValueError, AttributeError):
        return None
    multipliers = []
    for constraint in constraints:
        value = duals.get(constraint, 0.0)
        if not isfinite(value):
            return None
        multipliers.append(Fraction(max(0.0, value)).limit_denominator(1000))
    constant = sum((lam * row.base for lam, row in zip(multipliers, rows)), Fraction())
    coefficients = {}
    ax = {name: Fraction() for name in bounds}
    for lam, row in zip(multipliers, rows):
        for name, value in row.values.items():
            ax[name] += lam * value
        for index, value in row.binary.items():
            coefficients[index] = coefficients.get(index, Fraction()) + lam * value
    for name, (lb, ub) in bounds.items():
        quad = q.get(name, 0)
        linear = Fraction(c.get(name, 0)) - ax[name]
        if quad:
            minimum_at = max(Fraction(lb), min(Fraction(ub), -linear / (2 * quad)))
        else:
            minimum_at = Fraction(lb if linear >= 0 else ub)
        constant += quad * minimum_at * minimum_at + linear * minimum_at
    intercept = floor(constant)
    integral = {index: floor(value) for index, value in coefficients.items()}
    if abs(intercept) + sum(abs(v) for v in integral.values()) > cp_model.INT_MAX // 2:
        return None
    return intercept, integral
