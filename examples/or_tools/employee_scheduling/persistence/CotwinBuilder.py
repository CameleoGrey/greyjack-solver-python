from dataclasses import dataclass
from datetime import date
from itertools import combinations
from math import isqrt

from ortools.sat.python import cp_model

from ..cotwin.CotEmployeeSchedule import CotEmployeeSchedule
from ..domain.EmployeeSchedule import EmployeeSchedule


_HARD_NAMES = (
    "skill_penalty",
    "unavailable_penalty",
    "overlapping_penalty",
    "unrelax_penalty",
    "many_shifts_per_day_penalty",
)
_PREFERENCE_NAMES = ("undesired_date_penalty", "desired_date_reward")


@dataclass
class _ModelFacts:
    shift_count: int
    employee_count: int
    q_bound: int
    fairness_bound: int
    soft_lower: int
    soft_upper: int
    hard_bound: int
    hard_weight: int
    dates: list[date]
    pairs: list[tuple[int, int, int, int, int]]
    bounds: dict[str, int]


class CotwinBuilder:
    """Translate business facts into an exact hard/soft CP-SAT model."""

    def __init__(self, *, mode: str = "penalized"):
        if mode not in ("penalized", "strict"):
            raise ValueError("mode must be 'penalized' or 'strict'")
        self.mode = mode

    def build_cotwin(self, domain: EmployeeSchedule) -> CotEmployeeSchedule:
        domain.validate()
        facts = self._checked_model_facts(domain)
        model = cp_model.CpModel()
        assignments, indicators = self._add_assignments(
            model, domain, facts.employee_count
        )
        terms = self._collect_employee_terms(domain, facts.dates, indicators)
        self._add_pair_penalties(model, domain, facts.pairs, assignments, terms)
        components = self._add_component_variables(model, facts, terms)
        counts, fairness = self._add_fairness_constraints(model, facts, indicators)
        hard, soft = self._add_objective(model, facts, components, fairness)

        validation_error = model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        return CotEmployeeSchedule(
            model=model,
            assignment_variables=assignments,
            assignment_indicators=indicators,
            penalty_components=components,
            shift_counts=counts,
            fairness_cents=fairness,
            hard_penalty=hard,
            soft_penalty_cents=soft,
            hard_weight=facts.hard_weight,
            mode=self.mode,
        )

    def _checked_model_facts(self, domain: EmployeeSchedule) -> _ModelFacts:
        n = len(domain.shifts)
        m = len(domain.employees)
        # Q / m is the sum of squared deviations from the mean workload.
        q_bound = n * n * (m - 1) if m else 0
        fairness_bound = isqrt(10_000 * q_bound // m) if m else 0
        soft_lower = -100 * n
        soft_upper = 100 * n + fairness_bound
        hard_weight = soft_upper - soft_lower + 1 if self.mode == "penalized" else 0

        # Work in wall-clock minutes, without dependence on the host timezone.
        starts = [
            s.start.toordinal() * 1440 + s.start.hour * 60 + s.start.minute
            for s in domain.shifts
        ]
        ends = [
            s.end.toordinal() * 1440 + s.end.hour * 60 + s.end.minute
            for s in domain.shifts
        ]
        dates = [s.start.date() for s in domain.shifts]
        pairs = []
        for i, j in combinations(range(n), 2):
            overlap = min(ends[i], ends[j]) - max(starts[i], starts[j])
            overlapping = 2 * max(0, overlap)
            unrested = 2 * max(0, 600 + overlap) if overlap <= 0 else 0
            same_day = 2 * int(dates[i] == dates[j])
            if overlapping or unrested or same_day:
                pairs.append((i, j, overlapping, unrested, same_day))

        bounds = dict.fromkeys(_HARD_NAMES[:2], n)
        bounds.update(
            {
                name: sum(pair[k] for pair in pairs)
                for k, name in enumerate(_HARD_NAMES[2:], start=2)
            }
        )
        hard_bound = sum(bounds.values())
        # Check products and expression activities, not just final score values.
        safe_bound = cp_model.INT_MAX // 2
        arithmetic_bounds = [
            m * n * n,
            10_000 * q_bound,
            m * (fairness_bound + 1) ** 2,
            hard_bound,
            max(abs(soft_lower), abs(soft_upper)),
        ]
        if self.mode == "penalized":
            arithmetic_bounds.extend(
                (hard_weight, hard_weight * hard_bound + soft_upper - soft_lower)
            )
        if any(value > safe_bound for value in arithmetic_bounds):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")
        return _ModelFacts(
            n,
            m,
            q_bound,
            fairness_bound,
            soft_lower,
            soft_upper,
            hard_bound,
            hard_weight,
            dates,
            pairs,
            bounds,
        )

    @staticmethod
    def _add_assignments(
        model: cp_model.CpModel, domain: EmployeeSchedule, employee_count: int
    ) -> tuple[dict[int, cp_model.IntVar], dict[int, list[cp_model.IntVar]]]:
        assignments = {}
        indicators = {}
        for shift in domain.shifts:
            variable = model.new_int_var(0, employee_count - 1, f"employee_{shift.id}")
            row = [
                model.new_bool_var(f"assign_{shift.id}_{e}")
                for e in range(employee_count)
            ]
            model.add_exactly_one(row)
            model.add_map_domain(variable, row)
            assignments[shift.id] = variable
            indicators[shift.id] = row
            if shift.employee is not None:
                # Existing assignments are editable, advisory initialization only.
                model.add_hint(variable, shift.employee)
                for e, selected in enumerate(row):
                    model.add_hint(selected, int(e == shift.employee))
        return assignments, indicators

    @staticmethod
    def _collect_employee_terms(
        domain: EmployeeSchedule,
        dates: list[date],
        indicators: dict[int, list[cp_model.IntVar]],
    ) -> dict[str, list]:
        terms = {name: [] for name in (*_HARD_NAMES, *_PREFERENCE_NAMES)}
        employee_facts = [
            (
                set(e.skills),
                set(e.unavailable_dates),
                set(e.undesired_dates),
                set(e.desired_dates),
            )
            for e in domain.employees
        ]
        for i, shift in enumerate(domain.shifts):
            for e, (skills, unavailable, undesired, desired) in enumerate(
                employee_facts
            ):
                selected = indicators[shift.id][e]
                if shift.required_skill not in skills:
                    terms["skill_penalty"].append(selected)
                if dates[i] in unavailable:
                    terms["unavailable_penalty"].append(selected)
                if dates[i] in undesired:
                    terms["undesired_date_penalty"].append(selected)
                if dates[i] in desired:
                    terms["desired_date_reward"].append(-selected)
        return terms

    @staticmethod
    def _add_pair_penalties(
        model: cp_model.CpModel,
        domain: EmployeeSchedule,
        pairs: list[tuple[int, int, int, int, int]],
        assignments: dict[int, cp_model.IntVar],
        terms: dict[str, list],
    ) -> None:
        for i, j, overlapping, unrested, same_day in pairs:
            first = assignments[domain.shifts[i].id]
            second = assignments[domain.shifts[j].id]
            together = model.new_bool_var(f"same_employee_{i}_{j}")
            model.add(first == second).only_enforce_if(together)
            model.add(first != second).only_enforce_if(together.negated())
            for name, coefficient in zip(
                _HARD_NAMES[2:], (overlapping, unrested, same_day)
            ):
                if coefficient:
                    terms[name].append(coefficient * together)

    @staticmethod
    def _add_component_variables(
        model: cp_model.CpModel, facts: _ModelFacts, terms: dict[str, list]
    ) -> dict[str, cp_model.IntVar]:
        components = {}
        facts.bounds.update({name: facts.shift_count for name in _PREFERENCE_NAMES})
        for name, expressions in terms.items():
            lower, upper = (
                (-facts.shift_count, 0)
                if name == "desired_date_reward"
                else (0, facts.bounds[name])
            )
            variable = model.new_int_var(lower, upper, name)
            model.add(variable == sum(expressions))
            components[name] = variable
        return components

    @staticmethod
    def _add_fairness_constraints(
        model: cp_model.CpModel,
        facts: _ModelFacts,
        indicators: dict[int, list[cp_model.IntVar]],
    ) -> tuple[list[cp_model.IntVar], cp_model.IntVar]:
        n, m = facts.shift_count, facts.employee_count
        counts = []
        squares = []
        for e in range(m):
            count = model.new_int_var(0, n, f"shift_count_{e}")
            model.add(count == sum(row[e] for row in indicators.values()))
            square = model.new_int_var(0, n * n, f"shift_count_squared_{e}")
            model.add_multiplication_equality(square, [count, count])
            counts.append(count)
            squares.append(square)

        fairness = model.new_int_var(0, facts.fairness_bound, "fairness_cents")
        if n and m > 1:
            sum_squares = model.new_int_var(0, n * n, "sum_squared_counts")
            model.add(sum_squares == sum(squares))
            q = model.new_int_var(0, facts.q_bound, "scaled_variance")
            model.add(q == m * sum_squares - n * n)
            f_squared = model.new_int_var(
                0, facts.fairness_bound**2, "fairness_cents_squared"
            )
            model.add_multiplication_equality(f_squared, [fairness, fairness])
            # These inequalities uniquely encode floor(100 * sqrt(Q / m)).
            model.add(m * f_squared <= 10_000 * q)
            model.add(10_000 * q <= m * (f_squared + 2 * fairness + 1) - 1)
        return counts, fairness

    def _add_objective(
        self,
        model: cp_model.CpModel,
        facts: _ModelFacts,
        components: dict[str, cp_model.IntVar],
        fairness: cp_model.IntVar,
    ) -> tuple[cp_model.IntVar, cp_model.IntVar]:
        hard = model.new_int_var(0, facts.hard_bound, "hard_penalty")
        model.add(hard == sum(components[name] for name in _HARD_NAMES))
        soft = model.new_int_var(
            facts.soft_lower, facts.soft_upper, "soft_penalty_cents"
        )
        model.add(
            soft == 100 * sum(components[name] for name in _PREFERENCE_NAMES) + fairness
        )
        if self.mode == "strict":
            for name in _HARD_NAMES:
                model.add(components[name] == 0)
            model.add(hard == 0)
            model.minimize(soft)
        else:
            # Signed preferences remain below any improvement in hard score.
            model.minimize(facts.hard_weight * hard + soft)
        return hard, soft
