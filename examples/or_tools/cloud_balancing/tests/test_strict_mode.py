import io
import unittest
from contextlib import redirect_stdout

from examples.or_tools.cloud_balancing.domain.Computer import Computer
from examples.or_tools.cloud_balancing.domain.Process import Process
from examples.or_tools.cloud_balancing.domain.ScheduleCB import ScheduleCB
from examples.or_tools.cloud_balancing.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.cloud_balancing.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.cloud_balancing.solver.CloudBalancingSolver import (
    CloudBalancingSolver,
)


class StrictModeTests(unittest.TestCase):
    def solve(self, domain: ScheduleCB, mode: str):
        cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
        with redirect_stdout(io.StringIO()):
            return CloudBalancingSolver(
                workers=1, no_improvement_seconds=2, time_limit=5
            ).solve(cotwin)

    def test_strict_minimizes_cost_among_capacity_feasible_assignments(self):
        domain = ScheduleCB(
            [Computer(10, 1, 1, 1, 1), Computer(20, 2, 2, 2, 5)],
            [Process(100, 1, 1, 1), Process(200, 1, 1, 1)],
        )
        result = self.solve(domain, "strict")
        self.assertEqual(result.status, "OPTIMAL")
        self.assertEqual((result.hard_penalty, result.soft_cost), (0, 5))
        solved = DomainBuilder("unused.json").build_from_solution(result, domain)
        self.assertEqual(solved.calculate_metrics()["soft_cost"], 5)
        self.assertTrue(all(p.computer_id is None for p in domain.processes))

    def test_strict_returns_no_assignment_for_unavoidable_overload(self):
        domain = ScheduleCB(
            [Computer(10, 0, 0, 0, 7)], [Process(100, 1, 2, 3)]
        )
        penalized = self.solve(domain, "penalized")
        strict = self.solve(domain, "strict")
        self.assertEqual(penalized.hard_penalty, 6)
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)

    def test_strict_omits_unused_weight_overflow(self):
        domain = ScheduleCB(
            [Computer(10, 1000, 1000, 1000, 2**60)],
            [Process(100, 1000, 1000, 1000)],
        )
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder(mode="penalized").build_cotwin(domain)
        cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
        self.assertEqual(cotwin.mode, "strict")
        self.assertEqual(cotwin.hard_weight, 0)

    def test_invalid_mode(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="unknown")


if __name__ == "__main__":
    unittest.main()
