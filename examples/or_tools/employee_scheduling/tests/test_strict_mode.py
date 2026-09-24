import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta

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


class StrictModeTests(unittest.TestCase):
    def solve(self, domain: EmployeeSchedule, mode: str):
        cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
        with redirect_stdout(io.StringIO()):
            return EmployeeSchedulingSolver(
                workers=1, no_improvement_seconds=2, time_limit=5
            ).solve(cotwin)

    def test_strict_minimizes_signed_preferences_with_zero_hard_penalty(self):
        domain = EmployeeSchedule(
            [
                Employee("preferred", ["Nurse"], desired_dates=[START.date()]),
                Employee("other", ["Nurse"], undesired_dates=[START.date()]),
            ],
            [Shift(10, START, START + timedelta(hours=1), "Ward", "Nurse")],
        )
        result = self.solve(domain, "strict")
        self.assertEqual(result.status, "OPTIMAL")
        self.assertEqual((result.hard_penalty, result.soft_penalty_cents), (0, -30))
        solved = DomainBuilder().build_from_solution(result, domain)
        self.assertEqual(solved.calculate_metrics()["soft_penalty_cents"], -30)
        self.assertIsNone(domain.shifts[0].employee)

    def test_strict_returns_no_schedule_when_skill_is_unavailable(self):
        domain = EmployeeSchedule(
            [Employee("only", ["Nurse"])],
            [Shift(10, START, START + timedelta(hours=1), "Ward", "Surgeon")],
        )
        self.assertEqual(self.solve(domain, "penalized").hard_penalty, 1)
        strict = self.solve(domain, "strict")
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)

    def test_strict_enforces_same_employee_pair_rules(self):
        domain = EmployeeSchedule(
            [Employee("only", ["Nurse"])],
            [
                Shift(10, START, START + timedelta(hours=1), "A", "Nurse"),
                Shift(20, START, START + timedelta(hours=1), "B", "Nurse"),
            ],
        )
        self.assertGreater(self.solve(domain, "penalized").hard_penalty, 0)
        strict = self.solve(domain, "strict")
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)

    def test_invalid_mode(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="unknown")


if __name__ == "__main__":
    unittest.main()
