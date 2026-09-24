import io
import itertools
import random
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR, localcontext
from fractions import Fraction

from ortools.sat.python import cp_model

from examples.or_tools.employee_scheduling.domain.Employee import Employee
from examples.or_tools.employee_scheduling.domain.EmployeeSchedule import (
    EmployeeSchedule,
)
from examples.or_tools.employee_scheduling.domain.Shift import Shift
from examples.or_tools.employee_scheduling.persistence.CotwinBuilder import (
    CotwinBuilder,
)
from examples.or_tools.employee_scheduling.persistence.DomainBuilder import (
    DomainBuilder,
)
from examples.or_tools.employee_scheduling.solver.EmployeeSchedulingSolver import (
    EmployeeSchedulingSolver,
)


START = datetime(2026, 9, 28, 8)
DAY = START.date()
COMPONENT_NAMES = (
    "skill_penalty",
    "unavailable_penalty",
    "overlapping_penalty",
    "unrelax_penalty",
    "many_shifts_per_day_penalty",
    "undesired_date_penalty",
    "desired_date_reward",
)


def employee(name="Alex", skills=("Nurse",), **dates):
    return Employee(name=name, skills=list(skills), **dates)


def shift(identifier, start=START, minutes=60, required_skill="Nurse", **kwargs):
    return Shift(
        id=identifier,
        start=start,
        end=start + timedelta(minutes=minutes),
        location="Ward",
        required_skill=required_skill,
        **kwargs,
    )


def independent_metrics(domain, assignments):
    """Business oracle: intervals, exact rational variance, and Decimal sqrt.

    This deliberately imports no scoring helper and does not use the model's
    integer square-root identity or its component expressions.
    """
    components = dict.fromkeys(COMPONENT_NAMES, 0)
    counts = [0] * len(domain.employees)
    for current in domain.shifts:
        index = assignments[current.id]
        person = domain.employees[index]
        counts[index] += 1
        day = current.start.date()
        components["skill_penalty"] += current.required_skill not in person.skills
        components["unavailable_penalty"] += day in person.unavailable_dates
        components["undesired_date_penalty"] += day in person.undesired_dates
        components["desired_date_reward"] -= day in person.desired_dates
    for first, second in itertools.combinations(domain.shifts, 2):
        if assignments[first.id] != assignments[second.id]:
            continue
        intersection = min(first.end, second.end) - max(first.start, second.start)
        if intersection > timedelta(0):
            components["overlapping_penalty"] += 2 * (
                intersection // timedelta(minutes=1)
            )
        else:
            before, after = sorted((first, second), key=lambda value: value.start)
            rest = (after.start - before.end) // timedelta(minutes=1)
            components["unrelax_penalty"] += 2 * max(0, 600 - rest)
        components["many_shifts_per_day_penalty"] += 2 * (
            first.start.date() == second.start.date()
        )
    mean = Fraction(len(domain.shifts), len(counts)) if counts else Fraction(0)
    variance_sum = sum((Fraction(count) - mean) ** 2 for count in counts)
    with localcontext() as context:
        context.prec = 80
        fairness = (
            (Decimal(variance_sum.numerator) / Decimal(variance_sum.denominator)).sqrt()
            if counts
            else Decimal(0)
        )
        preference = (
            components["undesired_date_penalty"] + components["desired_date_reward"]
        )
        cents = int(
            ((Decimal(preference) + fairness) * 100).to_integral_value(
                rounding=ROUND_FLOOR
            )
        )
        fairness_cents = int((fairness * 100).to_integral_value(rounding=ROUND_FLOOR))
    hard = sum(components[key] for key in COMPONENT_NAMES[:5])
    return {
        **components,
        "hard_penalty": hard,
        "soft_penalty_cents": cents,
        "fairness_cents": fairness_cents,
        "unfairness_penalty": float(fairness),
        "shift_counts": counts,
        "mean_shift_count": float(mean),
        "business_feasible": hard == 0,
    }


def assigned_copy(domain, assignments):
    copied = deepcopy(domain)
    for current in copied.shifts:
        current.employee = assignments[current.id]
    return copied


class ScoringTests(unittest.TestCase):
    def solve(self, domain):
        with redirect_stdout(io.StringIO()):
            return EmployeeSchedulingSolver(
                workers=1, no_improvement_seconds=2, time_limit=5
            ).solve(CotwinBuilder().build_cotwin(domain))

    def assert_fixed_scores(self, domain, assignments):
        expected = independent_metrics(domain, assignments)
        cotwin = CotwinBuilder().build_cotwin(domain)
        for identifier, index in assignments.items():
            cotwin.model.add(cotwin.assignment_variables[identifier] == index)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.max_time_in_seconds = 5
        self.assertEqual(solver.solve(cotwin.model), cp_model.OPTIMAL)
        for name in COMPONENT_NAMES:
            self.assertEqual(
                solver.value(cotwin.penalty_components[name]), expected[name], name
            )
        self.assertEqual(solver.value(cotwin.hard_penalty), expected["hard_penalty"])
        self.assertEqual(
            solver.value(cotwin.soft_penalty_cents), expected["soft_penalty_cents"]
        )
        self.assertEqual(
            solver.value(cotwin.fairness_cents), expected["fairness_cents"]
        )
        self.assertEqual(
            [solver.value(value) for value in cotwin.shift_counts],
            expected["shift_counts"],
        )
        for identifier, row in cotwin.assignment_indicators.items():
            self.assertEqual(
                [solver.value(value) for value in row],
                [
                    int(index == assignments[identifier])
                    for index in range(len(domain.employees))
                ],
            )
        actual = assigned_copy(domain, assignments).calculate_metrics()
        for name, value in expected.items():
            if name in ("mean_shift_count", "unfairness_penalty"):
                self.assertAlmostEqual(actual[name], value, places=10, msg=name)
            else:
                self.assertEqual(actual[name], value, name)
        return expected

    def test_each_fixed_assignment_matches_independent_components(self):
        domain = EmployeeSchedule(
            [
                employee("Same name", unavailable_dates=[DAY], desired_dates=[DAY]),
                employee("Same name", skills=("Doctor",), undesired_dates=[DAY]),
            ],
            [
                shift(91, minutes=120),
                shift(-7, START + timedelta(minutes=60)),
                shift(410, START + timedelta(days=1)),
            ],
        )
        for choices in itertools.product(range(2), repeat=3):
            assignments = dict(zip((current.id for current in domain.shifts), choices))
            with self.subTest(assignments=assignments):
                self.assert_fixed_scores(domain, assignments)

    def test_interval_endpoints_double_counting_and_same_date_are_independent(self):
        cases = [
            (START + timedelta(minutes=30), 60, 60, 0, 2),
            (START, 30, 60, 0, 2),
            (START + timedelta(minutes=60), 60, 0, 1200, 2),
            (START + timedelta(minutes=659), 60, 0, 2, 2),
            (START + timedelta(minutes=660), 60, 0, 0, 2),
            (START + timedelta(days=1), 60, 0, 0, 0),
        ]
        for second_start, length, overlap, rest, same_day in cases:
            with self.subTest(second_start=second_start, length=length):
                domain = EmployeeSchedule(
                    [employee()], [shift(4), shift(99, second_start, length)]
                )
                expected = self.assert_fixed_scores(domain, {4: 0, 99: 0})
                self.assertEqual(expected["overlapping_penalty"], overlap)
                self.assertEqual(expected["unrelax_penalty"], rest)
                self.assertEqual(expected["many_shifts_per_day_penalty"], same_day)

    def test_overnight_constraints_use_real_end_and_start_calendar_date(self):
        first_start = datetime(2026, 9, 28, 22)
        next_day = first_start.date() + timedelta(days=1)
        domain = EmployeeSchedule(
            [employee(unavailable_dates=[next_day], desired_dates=[next_day])],
            [shift(8, first_start, 480), shift(-20, datetime(2026, 9, 29, 5), 120)],
        )
        metrics = self.assert_fixed_scores(domain, {8: 0, -20: 0})
        self.assertEqual(metrics["overlapping_penalty"], 120)
        self.assertEqual(metrics["unrelax_penalty"], 0)
        self.assertEqual(metrics["many_shifts_per_day_penalty"], 0)
        self.assertEqual(metrics["unavailable_penalty"], 1)
        self.assertEqual(metrics["desired_date_reward"], -1)

    def test_duplicate_and_conflicting_preference_dates_are_memberships(self):
        domain = EmployeeSchedule(
            [
                employee(
                    skills=(),
                    unavailable_dates=[DAY, DAY],
                    undesired_dates=[DAY, DAY],
                    desired_dates=[DAY, DAY],
                )
            ],
            [shift(12)],
        )
        metrics = self.assert_fixed_scores(domain, {12: 0})
        self.assertEqual(metrics["hard_penalty"], 2)
        self.assertEqual(metrics["undesired_date_penalty"], 1)
        self.assertEqual(metrics["desired_date_reward"], -1)
        self.assertEqual(metrics["soft_penalty_cents"], 0)

    def test_fairness_floor_including_negative_total_and_exact_square(self):
        cases = [
            (2, [0], 70),
            (3, [0], 81),
            (3, [0, 0], 163),
            (3, [0, 1, 2], 0),
            (9, [0, 0, 1], 200),
            (2, [0, 0, 0], 212),
        ]
        for count, choices, fairness_cents in cases:
            days = [DAY + timedelta(days=2 * offset) for offset in range(len(choices))]
            domain = EmployeeSchedule(
                [employee(str(index), desired_dates=days) for index in range(count)],
                [
                    shift(101 + 17 * offset, START + timedelta(days=2 * offset))
                    for offset in range(len(choices))
                ],
            )
            assignments = dict(zip((current.id for current in domain.shifts), choices))
            with self.subTest(count=count, choices=choices):
                metrics = self.assert_fixed_scores(domain, assignments)
                self.assertEqual(metrics["fairness_cents"], fairness_cents)
                self.assertEqual(
                    metrics["soft_penalty_cents"], fairness_cents - 100 * len(choices)
                )
        # A single preferred assignment among two employees scores -0.30,
        # not -0.29 (truncation toward zero) and not -0.29 (nearest rounding).

    def test_fixed_assignment_components_do_not_depend_on_optimization(self):
        domain = EmployeeSchedule(
            [employee(), employee("B")],
            [shift(18), shift(21, START + timedelta(days=2))],
        )
        cotwin = CotwinBuilder().build_cotwin(domain)
        cotwin.model.clear_objective()
        for variable in cotwin.assignment_variables.values():
            cotwin.model.add(variable == 0)
        solver = cp_model.CpSolver()
        self.assertEqual(solver.solve(cotwin.model), cp_model.OPTIMAL)
        self.assertEqual(solver.value(cotwin.fairness_cents), 141)
        self.assertEqual(solver.value(cotwin.soft_penalty_cents), 141)

    def test_fixed_assignment_components_cannot_take_alternate_values(self):
        domain = EmployeeSchedule(
            [employee(desired_dates=[DAY]), employee("B", skills=())],
            [shift(18), shift(21, START + timedelta(minutes=30))],
        )
        for assignments in ({18: 0, 21: 0}, {18: 0, 21: 1}):
            expected = independent_metrics(domain, assignments)
            for name in COMPONENT_NAMES + ("fairness_cents", "soft_penalty_cents"):
                with self.subTest(assignments=assignments, component=name):
                    cotwin = CotwinBuilder().build_cotwin(domain)
                    cotwin.model.clear_objective()
                    for identifier, index in assignments.items():
                        cotwin.model.add(
                            cotwin.assignment_variables[identifier] == index
                        )
                    variable = (
                        cotwin.penalty_components[name]
                        if name in COMPONENT_NAMES
                        else getattr(cotwin, name)
                    )
                    cotwin.model.add(variable != expected[name])
                    solver = cp_model.CpSolver()
                    solver.parameters.num_search_workers = 1
                    solver.parameters.max_time_in_seconds = 2
                    self.assertEqual(solver.solve(cotwin.model), cp_model.INFEASIBLE)

    def test_optimum_matches_exhaustive_enumeration(self):
        cases = [
            EmployeeSchedule([], []),
            EmployeeSchedule([employee(), employee("B")], []),
            EmployeeSchedule([employee(skills=())], [shift(1)]),
            EmployeeSchedule(
                [employee(), employee("B")],
                [shift(1), shift(9, START + timedelta(minutes=30))],
            ),
            EmployeeSchedule(
                [employee(desired_dates=[DAY]), employee("B", skills=("Doctor",))],
                [
                    shift(2),
                    shift(17, START + timedelta(days=1), required_skill="Doctor"),
                    shift(75, START + timedelta(days=2)),
                ],
            ),
            EmployeeSchedule(
                [
                    employee(
                        desired_dates=[DAY + timedelta(days=2 * i) for i in range(3)]
                    ),
                    employee("B"),
                ],
                [shift(100 + i, START + timedelta(days=2 * i)) for i in range(3)],
            ),
            EmployeeSchedule(
                [employee(), employee("B"), employee("C")],
                [
                    shift(11 + i, START + timedelta(hours=8 * i), minutes=480)
                    for i in range(4)
                ],
            ),
        ]
        for domain in cases:
            with self.subTest(employees=len(domain.employees), shifts=domain.shifts):
                scores = []
                for choices in itertools.product(
                    range(len(domain.employees)), repeat=len(domain.shifts)
                ):
                    metrics = independent_metrics(
                        domain,
                        dict(zip((current.id for current in domain.shifts), choices)),
                    )
                    scores.append(
                        (metrics["hard_penalty"], metrics["soft_penalty_cents"])
                    )
                optimum = min(scores)
                result = self.solve(domain)
                self.assertEqual(result.status, "OPTIMAL")
                self.assertTrue(result.has_solution)
                self.assertEqual(
                    (result.hard_penalty, result.soft_penalty_cents), optimum
                )
                replay = independent_metrics(domain, result.assignments)
                self.assertEqual(
                    (replay["hard_penalty"], replay["soft_penalty_cents"]), optimum
                )

    def test_hard_priority_over_favorable_soft_score(self):
        domain = EmployeeSchedule(
            [
                employee(undesired_dates=[DAY]),
                employee("B", skills=(), desired_dates=[DAY]),
            ],
            [shift(600)],
        )
        result = self.solve(domain)
        self.assertEqual(result.assignments, {600: 0})
        self.assertEqual((result.hard_penalty, result.soft_penalty_cents), (0, 170))

    def test_optimum_ties_are_compared_by_score_without_forcing_assignment(self):
        domain = EmployeeSchedule([employee(), employee("B")], [shift(5)])
        result = self.solve(domain)
        self.assertEqual((result.hard_penalty, result.soft_penalty_cents), (0, 70))
        self.assertIn(result.assignments[5], (0, 1))

    def test_preexisting_assignments_are_advisory_for_partial_and_full_inputs(self):
        for existing in ((0, None), (0, 0)):
            domain = EmployeeSchedule(
                [employee(skills=()), employee("Qualified")],
                [
                    shift(4, employee=existing[0]),
                    shift(12, START + timedelta(days=2), employee=existing[1]),
                ],
            )
            original = deepcopy(domain)
            with self.subTest(existing=existing):
                result = self.solve(domain)
                self.assertEqual(result.assignments, {4: 1, 12: 1})
                self.assertEqual(result.hard_penalty, 0)
                self.assertEqual(domain, original)

    def test_infeasible_business_schedule_still_has_complete_assignment(self):
        domain = EmployeeSchedule(
            [employee(skills=(), unavailable_dates=[DAY])], [shift(-7)]
        )
        result = self.solve(domain)
        self.assertTrue(result.has_solution)
        self.assertEqual(result.assignments, {-7: 0})
        metrics = (
            DomainBuilder().build_from_solution(result, domain).calculate_metrics()
        )
        self.assertFalse(metrics["business_feasible"])
        self.assertEqual(metrics["hard_penalty"], 2)


class DomainAndGenerationTests(unittest.TestCase):
    def test_round_trip_actual_ids_duplicate_names_and_input_immutability(self):
        domain = EmployeeSchedule(
            [employee("Same", skills=()), employee("Same")],
            [shift(820, employee=0), shift(-7, START + timedelta(days=2))],
        )
        original = deepcopy(domain)
        builder = DomainBuilder()
        copied = builder.build_from_domain(domain)
        self.assertEqual(copied, domain)
        self.assertIsNot(copied, domain)
        self.assertIsNot(copied.employees[0].skills, domain.employees[0].skills)
        with redirect_stdout(io.StringIO()):
            result = EmployeeSchedulingSolver(workers=1, time_limit=3).solve(
                CotwinBuilder().build_cotwin(domain)
            )
        solved = builder.build_from_solution(result, domain)
        self.assertEqual(
            {current.id: current.employee for current in solved.shifts}, {820: 1, -7: 1}
        )
        self.assertEqual(domain, original)
        self.assertIsNot(solved.employees[0], domain.employees[0])
        self.assertEqual(solved.calculate_metrics()["hard_penalty"], 0)

    def test_reconstruction_rejects_incomplete_invalid_and_inconsistent_results(self):
        domain = EmployeeSchedule([employee()], [shift(97)])
        with redirect_stdout(io.StringIO()):
            result = EmployeeSchedulingSolver(workers=1).solve(
                CotwinBuilder().build_cotwin(domain)
            )
        broken_results = [
            replace(result, assignments={}),
            replace(result, assignments={97: 0, 18: 0}),
            replace(result, assignments={97: -1}),
            replace(result, assignments={97: 1}),
            replace(result, assignments={97: True}),
            replace(result, assignments={97: None}),
            replace(result, hard_penalty=1),
            replace(result, soft_penalty_cents=1),
            replace(result, status="UNKNOWN", assignments=None),
        ]
        for broken in broken_results:
            with self.subTest(result=broken), self.assertRaises(ValueError):
                DomainBuilder().build_from_solution(broken, domain)

    def test_reconstruction_uses_builder_snapshot_after_initial_generation(self):
        builder = DomainBuilder(random_seed=37, dataset_size="small", start_date=DAY)
        domain = builder.build_domain_from_scratch()
        # Reconstruction is independently checked using a complete assignment;
        # solving the larger generator fixture is unnecessary for this contract.
        assignments = {
            current.id: index % len(domain.employees)
            for index, current in enumerate(domain.shifts)
        }
        metrics = independent_metrics(domain, assignments)
        from examples.or_tools.employee_scheduling.solver.EmployeeSchedulingSolution import (
            EmployeeSchedulingSolution,
        )

        result = EmployeeSchedulingSolution(
            status="FEASIBLE",
            assignments=assignments,
            hard_penalty=metrics["hard_penalty"],
            soft_penalty_cents=metrics["soft_penalty_cents"],
            elapsed_seconds=0,
            termination_reason="time_limit",
        )
        solved = builder.build_from_solution(result)
        self.assertEqual(
            [current.start for current in solved.shifts],
            [current.start for current in domain.shifts],
        )
        self.assertEqual(
            {current.id: current.employee for current in solved.shifts}, assignments
        )
        self.assertTrue(all(current.employee is None for current in domain.shifts))

    def test_metrics_require_complete_valid_assignment(self):
        for assignment in (None, True, -1, 2, "0"):
            domain = EmployeeSchedule(
                [employee(), employee("B")], [shift(1, employee=assignment)]
            )
            with self.subTest(assignment=assignment), self.assertRaises(ValueError):
                domain.calculate_metrics()

    def test_employee_date_defaults_are_not_shared(self):
        first, second = employee(), employee()
        first.unavailable_dates.append(DAY)
        first.undesired_dates.append(DAY)
        first.desired_dates.append(DAY)
        self.assertEqual(second.unavailable_dates, [])
        self.assertEqual(second.undesired_dates, [])
        self.assertEqual(second.desired_dates, [])

    def test_invalid_domains_fail_before_solving(self):
        valid = EmployeeSchedule([employee()], [shift(31)])
        invalid = [
            EmployeeSchedule([], valid.shifts),
            EmployeeSchedule(valid.employees, valid.shifts * 2),
        ]
        for target, field, value in (
            ("shift", "id", True),
            ("shift", "id", "31"),
            ("shift", "start", DAY),
            ("shift", "start", START.replace(second=1)),
            ("shift", "end", (START + timedelta(hours=1)).replace(microsecond=1)),
            ("shift", "start", START.replace(tzinfo=timezone.utc)),
            ("shift", "end", START),
            ("shift", "end", START - timedelta(minutes=1)),
            ("shift", "employee", True),
            ("shift", "employee", -1),
            ("shift", "employee", 1),
            ("employee", "unavailable_dates", [START]),
            ("employee", "undesired_dates", ["2026-09-28"]),
            ("employee", "desired_dates", [None]),
        ):
            domain = deepcopy(valid)
            setattr(
                domain.shifts[0] if target == "shift" else domain.employees[0],
                field,
                value,
            )
            invalid.append(domain)
        for domain in invalid:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                CotwinBuilder().build_cotwin(domain)

    def test_integer_bound_failure_is_reported_before_native_solving(self):
        domain = EmployeeSchedule(
            [employee(), employee("B")],
            [
                Shift(
                    index, datetime.min, datetime(9999, 12, 31, 23, 59), "Ward", "Nurse"
                )
                for index in range(200)
            ],
        )
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder().build_cotwin(domain)

    def test_empty_schedule_metrics_are_defined(self):
        for people in ([], [employee(), employee("B")]):
            domain = EmployeeSchedule(people, [])
            metrics = domain.calculate_metrics()
            self.assertEqual(metrics["hard_penalty"], 0)
            self.assertEqual(metrics["soft_penalty_cents"], 0)
            self.assertEqual(metrics["fairness_cents"], 0)
            self.assertEqual(metrics["shift_counts"], [0] * len(people))
            self.assertEqual(metrics["mean_shift_count"], 0)
            self.assertTrue(metrics["business_feasible"])

    def test_generator_fixed_seed_and_date_match_source_shape(self):
        for size, seed, employees, shifts in (
            ("small", 37, 15, 139),
            ("small", 45, 15, 138),
            ("large", 37, 50, 935),
            ("large", 45, 50, 914),
        ):
            with self.subTest(size=size, seed=seed):
                builder = DomainBuilder(
                    random_seed=seed, dataset_size=size, start_date=DAY
                )
                first = builder.build_domain_from_scratch()
                second = builder.build_domain_from_scratch()
                self.assertEqual(first, second)
                self.assertIsNot(first, second)
                self.assertEqual(
                    (len(first.employees), len(first.shifts)), (employees, shifts)
                )
                self.assertEqual(
                    min(current.start.date() for current in first.shifts), DAY
                )
                self.assertEqual(len({current.id for current in first.shifts}), shifts)
                self.assertTrue(
                    all(current.employee is None for current in first.shifts)
                )

    def test_generator_does_not_use_or_mutate_process_random_state(self):
        state = random.getstate()
        try:
            random.seed(7)
            before = random.getstate()
            first = DomainBuilder(
                random_seed=45, dataset_size="small", start_date=DAY
            ).build_domain_from_scratch()
            self.assertEqual(random.getstate(), before)
            random.seed(90210)
            random.random()
            second = DomainBuilder(
                random_seed=45, dataset_size="small", start_date=DAY
            ).build_domain_from_scratch()
            self.assertEqual(first, second)
            different = DomainBuilder(
                random_seed=37, dataset_size="small", start_date=DAY
            ).build_domain_from_scratch()
            self.assertNotEqual(first, different)
        finally:
            random.setstate(state)

    def test_invalid_generation_options(self):
        for options in (
            {"dataset_size": "medium"},
            {"random_seed": True},
            {"random_seed": 1.5},
            {"start_date": START},
            {"start_date": "2026-09-28"},
            {"start_date": date.max},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                DomainBuilder(**options).build_domain_from_scratch()


if __name__ == "__main__":
    unittest.main()
