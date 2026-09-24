import itertools
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from examples.or_tools.vrp_cp_sat.domain import Customer, Vehicle, VehicleRoutingPlan
from examples.or_tools.vrp_cp_sat.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.vrp_cp_sat.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.vrp_cp_sat.solver.VRPSolution import VRPSolution
from examples.or_tools.vrp_cp_sat.solver.VRPSolver import VRPSolver


ROOT = Path(__file__).resolve().parents[4]
DATASET = ROOT / "data/vehiclerouting/belgium-tw-d2-n50-k10.vrp"


def small_domain() -> VehicleRoutingPlan:
    locations = [
        Customer(100, "D1", 0.0, 0.0, 0, 0, 12, 0),
        Customer(200, "D2", 0.0, 1.0, 0, 0, 12, 0),
        Customer(7, "A", 1.0, 0.0, 3, 0, 4, 2),
        Customer(9, "B", 1.0, 1.0, 4, 3, 7, 3),
        Customer(11, "C", 2.0, 0.0, 5, 5, 8, 2),
    ]
    return VehicleRoutingPlan(
        "small",
        locations,
        [100, 200],
        [Vehicle(100, 5, 0, 12), Vehicle(200, 5, 0, 12)],
        [
            [0, 7, 2, 8, 4],
            [6, 0, 5, 2, 9],
            [3, 4, 0, 1, 3],
            [8, 3, 2, 0, 4],
            [5, 8, 2, 3, 0],
        ],
        True,
    )


def best_by_enumeration(domain: VehicleRoutingPlan) -> tuple[int, int, int]:
    customers = [
        domain.location_by_id[customer_id]
        for customer_id in sorted(domain.customer_ids)
    ]
    best = None
    for owners in itertools.product(range(len(domain.vehicles)), repeat=len(customers)):
        groups = [
            [customer for customer, owner in zip(customers, owners) if owner == vehicle]
            for vehicle in range(len(domain.vehicles))
        ]
        for routes in itertools.product(
            *(itertools.permutations(group) for group in groups)
        ):
            candidate = deepcopy(domain)
            for vehicle, route in zip(candidate.vehicles, routes):
                vehicle.customer_list = list(route)
            metrics = candidate.calculate_metrics()
            score = (
                metrics["hard_penalty"],
                metrics["medium_penalty"],
                metrics["distance"],
            )
            if best is None or score < best:
                best = score
    return best


class VRPTests(unittest.TestCase):
    def test_mtz_and_scores_match_exhaustive_multi_depot_search(self):
        domain = small_domain()
        expected = best_by_enumeration(domain)
        cotwin = CotwinBuilder().build_cotwin(domain)
        solution = VRPSolver(workers=1, time_limit=10).solve(cotwin)
        self.assertEqual(solution.status, "OPTIMAL")
        self.assertEqual(
            (solution.hard_penalty, solution.medium_penalty, solution.distance),
            expected,
        )
        solved = DomainBuilder("unused").build_from_solution(solution, domain)
        self.assertEqual(sum(len(v.customer_list) for v in solved.vehicles), 3)
        self.assertTrue(all(not v.customer_list for v in domain.vehicles))
        self.assertEqual(
            {stop.id for vehicle in solved.vehicles for stop in vehicle.customer_list},
            {7, 9, 11},
        )

    def test_mtz_excludes_disconnected_customer_cycle(self):
        locations = [Customer(100, "D", 0.0, 0.0, 0)] + [
            Customer(i, str(i), 0.0, float(i), 0) for i in (1, 2, 3)
        ]
        matrix = [[0, 100, 100, 100]] + [
            [100, *[0 for _ in range(3)]] for _ in range(3)
        ]
        domain = VehicleRoutingPlan(
            "cycle", locations, [100], [Vehicle(100, 1)], matrix, False
        )
        solution = VRPSolver(workers=1, time_limit=5).solve(
            CotwinBuilder(use_greedy_hints=False).build_cotwin(domain)
        )
        self.assertEqual(solution.status, "OPTIMAL")
        self.assertEqual(solution.distance, 200)
        self.assertEqual(set(solution.routes[0]), {1, 2, 3})

    def test_overload_and_time_replay_ignore_travel_duration(self):
        domain = VehicleRoutingPlan(
            "late",
            [
                Customer(100, "D", 0.0, 0.0, 0, 0, 13, 0),
                Customer(1, "A", 0.0, 1.0, 2, 10, 11, 2),
                Customer(2, "B", 1.0, 0.0, 2, 0, 13, 2),
            ],
            [100],
            [Vehicle(100, 2, 0, 13)],
            [[0, 10000, 10000], [10000, 0, 10000], [10000, 10000, 0]],
            True,
        )
        domain.vehicles[0].customer_list = [domain.locations[2], domain.locations[1]]
        metrics = domain.calculate_metrics()
        self.assertEqual(
            (metrics["hard_penalty"], metrics["medium_penalty"], metrics["distance"]),
            (2, 1, 30000),
        )
        domain.vehicles[0].customer_list = []
        solution = VRPSolver(workers=1, time_limit=5).solve(
            CotwinBuilder().build_cotwin(domain)
        )
        self.assertEqual((solution.hard_penalty, solution.medium_penalty), (2, 1))
        DomainBuilder("unused").build_from_solution(solution, domain)

    def test_non_windowed_customer_can_leave_a_vehicle_unused(self):
        domain = VehicleRoutingPlan(
            "basic",
            [Customer(90, "D", 0.0, 0.0, 0), Customer(17, "A", 1.0, 1.0, 2)],
            [90],
            [Vehicle(90, 5), Vehicle(90, 5)],
            [[0, 4], [7, 0]],
            False,
        )
        solution = VRPSolver(workers=1, time_limit=5).solve(
            CotwinBuilder().build_cotwin(domain)
        )
        self.assertEqual(solution.status, "OPTIMAL")
        self.assertEqual(
            (solution.hard_penalty, solution.medium_penalty, solution.distance),
            (0, 0, 11),
        )
        self.assertEqual(sum(bool(route) for route in solution.routes), 1)

    def test_reconstruction_rejects_incomplete_or_inconsistent_routes(self):
        domain = small_domain()
        builder = DomainBuilder("unused")
        with self.assertRaisesRegex(ValueError, "omit customers"):
            builder.build_from_solution(
                VRPSolution("FEASIBLE", ((7,), (9,)), 0, 0, 0, 0.0, "test"),
                domain,
            )
        with self.assertRaisesRegex(ValueError, "differ"):
            builder.build_from_solution(
                VRPSolution("FEASIBLE", ((7, 9), (11,)), 0, 0, 0, 0.0, "test"),
                domain,
            )
        with self.assertRaisesRegex(ValueError, "without an incumbent"):
            builder.build_from_solution(
                VRPSolution("UNKNOWN", None, None, None, None, 0.0, "test"),
                domain,
            )

    def test_checked_in_parser_and_cli(self):
        domain = DomainBuilder(DATASET).build_domain_from_scratch()
        self.assertEqual(
            (len(domain.locations), len(domain.customer_ids), len(domain.vehicles)),
            (50, 48, 10),
        )
        self.assertEqual(domain.depot_ids, [782, 1655])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tiny-k2.vrp"
            path.write_text(
                "NAME: tiny-k2\nTYPE: CVRPTW\nDIMENSION: 3\n"
                "EDGE_WEIGHT_TYPE: EUC_2D\nCAPACITY: 3\nNODE_COORD_SECTION\n"
                "100 0 0 D\n10 0 1 A\n20 1 0 B\nDEMAND_SECTION\n"
                "100 0 0 20 0\n10 2 0 10 1\n20 2 0 10 1\n"
                "DEPOT_SECTION\n100\n-1\nEOF\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "examples.or_tools.vrp_cp_sat.scripts.solve_vrp",
                    "--input",
                    str(path),
                    "--workers",
                    "1",
                    "--time-limit",
                    "5",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Unique stops (excluding depots): 2", result.stdout)
            self.assertIn("Capacity overload: 0", result.stdout)

    def test_invalid_edge_type_and_integer_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad-k1.vrp"
            path.write_text(
                "NAME: bad-k1\nDIMENSION: 1\nEDGE_WEIGHT_TYPE: EXPLICIT\n"
                "CAPACITY: 1\nNODE_COORD_SECTION\n1 0 0\n"
                "DEMAND_SECTION\n1 0\nDEPOT_SECTION\n1\n-1\nEOF\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "EUC_2D"):
                DomainBuilder(path).build_domain_from_scratch()
        domain = VehicleRoutingPlan(
            "overflow",
            [Customer(0, "D", 0.0, 0.0, 0), Customer(1, "A", 0.0, 1.0, 1)],
            [0],
            [Vehicle(0, 1)],
            [[0, 2**61], [2**61, 0]],
            False,
        )
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder().build_cotwin(domain)


if __name__ == "__main__":
    unittest.main()
