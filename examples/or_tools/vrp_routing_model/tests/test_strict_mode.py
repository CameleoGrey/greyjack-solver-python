import io
import unittest
from contextlib import redirect_stdout

from examples.or_tools.vrp_routing_model.domain import (
    Customer,
    Vehicle,
    VehicleRoutingPlan,
)
from examples.or_tools.vrp_routing_model.persistence.CotwinBuilder import (
    CotwinBuilder,
)
from examples.or_tools.vrp_routing_model.persistence.DomainBuilder import (
    DomainBuilder,
)
from examples.or_tools.vrp_routing_model.solver.VRPSolver import VRPSolver


def domain(capacity: int = 5) -> VehicleRoutingPlan:
    return VehicleRoutingPlan(
        "strict-demo",
        [
            Customer(100, "Depot", 0, 0, 0, 0, 10, 0),
            Customer(7, "A", 0, 1, 2, 0, 5, 2),
            Customer(9, "B", 1, 0, 3, 3, 10, 2),
        ],
        [100],
        [Vehicle(100, capacity, 0, 10)],
        [[0, 4, 3], [5, 0, 2], [6, 1, 0]],
        True,
    )


class StrictModeTests(unittest.TestCase):
    def solve(self, problem: VehicleRoutingPlan, mode: str):
        cotwin = CotwinBuilder(mode=mode).build_cotwin(problem)
        with redirect_stdout(io.StringIO()):
            return VRPSolver(0.05, 0.5).solve(cotwin)

    def test_strict_minimizes_distance_over_capacity_and_time_feasible_routes(self):
        problem = domain()
        result = self.solve(problem, "strict")
        self.assertTrue(result.has_solution)
        self.assertEqual((result.hard_penalty, result.medium_penalty, result.distance),
                         (0, 0, 12))
        self.assertEqual(result.objective, 12)
        self.assertEqual(result.routes, ((7, 9),))
        solved = DomainBuilder("unused").build_from_solution(result, problem)
        self.assertEqual(solved.calculate_metrics()["distance"], 12)
        self.assertFalse(problem.vehicles[0].customer_list)

    def test_strict_rejects_unavoidable_overload(self):
        problem = domain(capacity=4)
        self.assertEqual(self.solve(problem, "penalized").hard_penalty, 1)
        strict = self.solve(problem, "strict")
        self.assertFalse(strict.has_solution)
        self.assertIn(strict.status, ("ROUTING_FAIL", "ROUTING_INFEASIBLE"))
        self.assertIn(strict.termination_reason, ("no_solution", "infeasible"))

    def test_strict_rejects_impossible_service_window_without_crashing(self):
        problem = domain()
        problem.locations[1] = Customer(7, "A", 0, 1, 2, 0, 1, 2)
        self.assertGreater(self.solve(problem, "penalized").medium_penalty, 0)
        strict = self.solve(problem, "strict")
        self.assertFalse(strict.has_solution)
        self.assertEqual(strict.status, "ROUTING_INFEASIBLE")

    def test_strict_omits_unused_weight_overflow(self):
        problem = VehicleRoutingPlan(
            "large-clock",
            [
                Customer(100, "Depot", 0, 0, 0, 0, 1, 0),
                Customer(7, "A", 0, 1, 1000, 0, 0, 10**12),
            ],
            [100],
            [Vehicle(100, 0, 0, 1)],
            [[0, 1_000_000], [1_000_000, 0]],
            True,
        )
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder(mode="penalized").build_cotwin(problem)
        cotwin = CotwinBuilder(mode="strict").build_cotwin(problem)
        self.assertEqual(cotwin.mode, "strict")
        self.assertEqual(cotwin.objective_bound, 2_000_000)

    def test_invalid_mode(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="unknown")


if __name__ == "__main__":
    unittest.main()
