import itertools
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from io import StringIO
from pathlib import Path

from examples.or_tools.vrp_routing_model.domain import (
    Customer,
    Vehicle,
    VehicleRoutingPlan,
)
from examples.or_tools.vrp_routing_model.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.vrp_routing_model.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.vrp_routing_model.solver.VRPSolver import VRPSolver


ROOT = Path(__file__).resolve().parents[4]
DATASET = ROOT / "data/vehiclerouting/belgium-tw-d2-n50-k10.vrp"
LARGE_DATASET = ROOT / "data/vehiclerouting/belgium-tw-d8-n1000-k40.vrp"


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
        [[0, 7, 2, 8, 4], [6, 0, 5, 2, 9], [3, 4, 0, 1, 3],
         [8, 3, 2, 0, 4], [5, 8, 2, 3, 0]],
        True,
    )


def exact_score(domain: VehicleRoutingPlan) -> tuple[int, int, int]:
    customers = [domain.location_by_id[customer_id] for customer_id in sorted(domain.customer_ids)]
    best = None
    for owners in itertools.product(range(len(domain.vehicles)), repeat=len(customers)):
        groups = [
            [customer for customer, owner in zip(customers, owners) if owner == vehicle]
            for vehicle in range(len(domain.vehicles))
        ]
        for routes in itertools.product(*(itertools.permutations(group) for group in groups)):
            candidate = deepcopy(domain)
            for vehicle, route in zip(candidate.vehicles, routes):
                vehicle.customer_list = list(route)
            metrics = candidate.calculate_metrics()
            score = (metrics["hard_penalty"], metrics["medium_penalty"], metrics["distance"])
            if best is None or score < best:
                best = score
    return best


def explicit_file(matrix: str = "0 7 2\n6 0 5\n3 4 0") -> str:
    return (
        "NAME: explicit-k1\nTYPE: CVRP\nDIMENSION: 3\n"
        "EDGE_WEIGHT_TYPE: EXPLICIT\nEDGE_WEIGHT_FORMAT: FULL_MATRIX\n"
        "CAPACITY: 4\nNODE_COORD_SECTION\n"
        "100 0 0 Depot\n7 0 1 A\n9 1 0 B\n"
        "DEMAND_SECTION\n100 0\n7 2\n9 2\n"
        f"EDGE_WEIGHT_SECTION\n{matrix}\n"
        "DEPOT_SECTION\n100\n-1\nEOF\n"
    )


class RoutingModelVRPTests(unittest.TestCase):
    def test_multi_depot_score_matches_independent_enumeration_and_replay(self):
        domain = small_domain()
        expected = exact_score(domain)
        with redirect_stdout(StringIO()):
            solution = VRPSolver(0.1, 1).solve(CotwinBuilder().build_cotwin(domain))
        self.assertTrue(solution.has_solution)
        self.assertEqual(
            (solution.hard_penalty, solution.medium_penalty, solution.distance), expected
        )
        solved = DomainBuilder("unused").build_from_solution(solution, domain)
        self.assertEqual(sum(len(v.customer_list) for v in solved.vehicles), 3)
        self.assertTrue(all(not vehicle.customer_list for vehicle in domain.vehicles))
        self.assertEqual(
            {stop.id for vehicle in solved.vehicles for stop in vehicle.customer_list},
            {7, 9, 11},
        )

    def test_lateness_uses_service_not_travel_and_can_exceed_window(self):
        domain = VehicleRoutingPlan(
            "late",
            [
                Customer(100, "D", 0, 0, 0, 0, 13, 0),
                Customer(1, "A", 0, 1, 2, 0, 2, 5),
            ],
            [100],
            [Vehicle(100, 1, 0, 13)],
            [[0, 10000], [10000, 0]],
            True,
        )
        with redirect_stdout(StringIO()):
            solution = VRPSolver(0.05, 0.5).solve(CotwinBuilder().build_cotwin(domain))
        self.assertTrue(solution.has_solution)
        self.assertEqual(
            (solution.hard_penalty, solution.medium_penalty, solution.distance),
            (1, 3, 20000),
        )
        DomainBuilder("unused").build_from_solution(solution, domain)

    def test_exact_time_units_preserve_large_business_penalties(self):
        unit = 10**12
        domain = VehicleRoutingPlan(
            "large-clock",
            [
                Customer(100, "D", 0, 0, 0, 0, 0, 0),
                Customer(1, "A", 0, 1, 1000, 0, 0, unit),
            ],
            [100],
            [Vehicle(100, 0, 0, 0)],
            [[0, 1_000_000], [1_000_000, 0]],
            True,
        )
        cotwin = CotwinBuilder().build_cotwin(domain)
        self.assertEqual(cotwin.time_scale, unit)
        with redirect_stdout(StringIO()):
            solution = VRPSolver(0.05, 0.5).solve(cotwin)
        self.assertEqual(
            (solution.hard_penalty, solution.medium_penalty, solution.distance),
            (1000, 2 * unit, 2_000_000),
        )
        DomainBuilder("unused").build_from_solution(solution, domain)

    def test_non_windowed_vehicles_can_be_unused(self):
        domain = VehicleRoutingPlan(
            "basic",
            [Customer(90, "D", 0, 0, 0), Customer(17, "A", 1, 1, 2)],
            [90],
            [Vehicle(90, 5), Vehicle(90, 5)],
            [[0, 4], [7, 0]],
            False,
        )
        with redirect_stdout(StringIO()):
            solution = VRPSolver(0.05, 0.5).solve(CotwinBuilder().build_cotwin(domain))
        self.assertTrue(solution.has_solution)
        self.assertEqual(
            (solution.hard_penalty, solution.medium_penalty, solution.distance),
            (0, 0, 11),
        )
        self.assertEqual(sum(bool(route) for route in solution.routes), 1)

    def test_explicit_asymmetric_matrix_and_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "explicit-k1.vrp"
            path.write_text(explicit_file(), encoding="utf-8")
            domain = DomainBuilder(path).build_domain_from_scratch()
            self.assertEqual(domain.distance_matrix[0][1], 7)
            self.assertEqual(domain.distance_matrix[1][0], 6)
            path.write_text(explicit_file("0 7\n2 6 0 5\n3 4 0"), encoding="utf-8")
            self.assertEqual(
                DomainBuilder(path).build_domain_from_scratch().distance_matrix,
                domain.distance_matrix,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "examples.or_tools.vrp_routing_model.scripts.solve_vrp",
                    "--input", str(path),
                    "--time-limit", "0.5",
                    "--no-improvement-seconds", "0.05",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Solution distance: 12", result.stdout)
            self.assertIn("Unique stops (excluding depots): 2", result.stdout)
            self.assertIn("Depot --> B --> A --> Depot", result.stdout)

    def test_reconstruction_rejects_missing_repeated_or_wrong_score(self):
        domain = small_domain()
        with redirect_stdout(StringIO()):
            solution = VRPSolver(0.05, 0.5).solve(CotwinBuilder().build_cotwin(domain))
        builder = DomainBuilder("unused")
        with self.assertRaisesRegex(ValueError, "omit customers"):
            builder.build_from_solution(replace(solution, routes=((7,), (9,))), domain)
        with self.assertRaisesRegex(ValueError, "multiple stops"):
            builder.build_from_solution(replace(solution, routes=((7, 9), (9, 11))), domain)
        with self.assertRaisesRegex(ValueError, "differ"):
            builder.build_from_solution(replace(solution, distance=0), domain)
        with self.assertRaisesRegex(ValueError, "without an incumbent"):
            builder.build_from_solution(
                replace(solution, routes=None, hard_penalty=None), domain
            )

    def test_parser_rejects_malformed_explicit_data_and_unsafe_bounds(self):
        malformed = (
            (explicit_file("0 7 2\n6 0 5\n3 4"), "DIMENSION × DIMENSION"),
            (explicit_file("0 7 2\n6 0 5\n3 4 1.5"), "integers"),
            (explicit_file("0 7 2\n6 0 5\n3 -4 0"), "nonnegative"),
            (explicit_file().replace("FULL_MATRIX", "UPPER_ROW"), "FULL_MATRIX"),
            (explicit_file().replace("EDGE_WEIGHT_SECTION\n", ""), "EDGE_WEIGHT_SECTION"),
            (explicit_file().replace("9 1 0 B", "7 1 0 B"), "Duplicate location ID"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad-k1.vrp"
            for contents, message in malformed:
                with self.subTest(message=message):
                    path.write_text(contents, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        DomainBuilder(path).build_domain_from_scratch()
        overflow = VehicleRoutingPlan(
            "overflow",
            [Customer(0, "D", 0, 0, 0), Customer(1, "A", 0, 1, 1)],
            [0],
            [Vehicle(0, 1)],
            [[0, 2**61], [2**61, 0]],
            False,
        )
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder().build_cotwin(overflow)

    def test_improvements_are_strict_and_limits_stop_search(self):
        domain = small_domain()
        output = StringIO()
        with redirect_stdout(output):
            idle_result = VRPSolver(0.05, 1).solve(CotwinBuilder().build_cotwin(domain))
        self.assertEqual(idle_result.termination_reason, "no_improvement")
        score_lines = [line for line in output.getvalue().splitlines() if "New best solution" in line]
        self.assertTrue(score_lines)
        scores = [
            tuple(int(value) for value in re.findall(
                r"hard_penalty=(\d+), medium_penalty=(\d+), distance=(\d+)", line
            )[0])
            for line in score_lines
        ]
        self.assertTrue(all(right < left for left, right in zip(scores, scores[1:])))
        with redirect_stdout(StringIO()):
            capped_result = VRPSolver(5, 0.05).solve(CotwinBuilder().build_cotwin(domain))
        self.assertEqual(capped_result.termination_reason, "time_limit")

    def test_checked_in_dataset_parser(self):
        domain = DomainBuilder(DATASET).build_domain_from_scratch()
        self.assertEqual(
            (len(domain.locations), len(domain.customer_ids), len(domain.vehicles)),
            (50, 48, 10),
        )
        self.assertEqual(domain.depot_ids, [782, 1655])

    def test_large_checked_in_dataset_builds_with_exact_time_units(self):
        domain = DomainBuilder(LARGE_DATASET).build_domain_from_scratch()
        cotwin = CotwinBuilder().build_cotwin(domain)
        self.assertEqual(len(cotwin.customer_indices), 992)
        self.assertEqual(cotwin.time_scale, 300)
        self.assertLess(cotwin.objective_bound, ((1 << 63) - 1) // 4)


if __name__ == "__main__":
    unittest.main()
