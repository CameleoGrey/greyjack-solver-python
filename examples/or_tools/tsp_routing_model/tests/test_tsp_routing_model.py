import io
import itertools
import math
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from examples.or_tools.tsp_routing_model.domain import (
    Location,
    TravelSchedule,
    Vehicle,
)
from examples.or_tools.tsp_routing_model.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.tsp_routing_model.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.tsp_routing_model.solver.TSPSolution import TSPSolution
from examples.or_tools.tsp_routing_model.solver.TSPSolver import TSPSolver


ROOT = Path(__file__).resolve().parents[4]
DATASET = ROOT / "data/tsp/pcb442.tsp"


def small_domain(matrix: list[list[int]] | None = None) -> TravelSchedule:
    locations = [
        Location(100, "Depot", 0.0, 0.0),
        Location(7, "A", 1.0, 0.0),
        Location(9, "B", 0.0, 1.0),
        Location(11, "C", 1.0, 1.0),
    ]
    return TravelSchedule(
        "small",
        Vehicle(100),
        locations,
        matrix
        or [
            [0, 4, 9, 8],
            [6, 0, 3, 7],
            [5, 8, 0, 2],
            [4, 9, 6, 0],
        ],
        1,
    )


def best_distance_by_enumeration(domain: TravelSchedule) -> int:
    matrix = domain.distance_matrix
    return min(
        sum(matrix[left][right] for left, right in zip(tour, tour[1:]))
        for stops in itertools.permutations(range(1, len(domain.locations_list)))
        for tour in ([0, *stops, 0],)
    )


class TSPRoutingModelTests(unittest.TestCase):
    def test_directed_optimum_matches_enumeration_and_independent_replay(self):
        domain = small_domain()
        expected = best_distance_by_enumeration(domain)
        cotwin = CotwinBuilder().build_cotwin(domain)
        self.assertEqual(len(cotwin.callbacks), 1)
        with redirect_stdout(io.StringIO()) as output:
            solution = TSPSolver(0.1, 1).solve(cotwin)
        self.assertTrue(solution.has_solution)
        self.assertEqual(solution.distance, expected)
        self.assertEqual(set(solution.tour_ids), {7, 9, 11})
        self.assertIn("New best solution #1:", output.getvalue())
        solved = DomainBuilder("unused").build_from_solution(solution, domain)
        self.assertEqual(solved.calculate_metrics()["distance"], expected)
        self.assertIsNone(domain.vehicle.trip_path)

    def test_explicit_decimal_matrix_and_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tiny.tsp"
            path.write_text(
                "NAME : tiny\nTYPE : TSP\nDIMENSION : 3\n"
                "EDGE_WEIGHT_TYPE : EXPLICIT\nEDGE_WEIGHT_FORMAT : FULL_MATRIX\n"
                "NODE_COORD_SECTION\n100 0 0 Depot\n7 1 0 A\n9 0 1 B\n"
                "EDGE_WEIGHT_SECTION\n0 1.25 10\n2.50 0 3\n4 1 0\nEOF\n",
                encoding="utf-8",
            )
            domain = DomainBuilder(path).build_domain_from_scratch()
            self.assertEqual(domain.distance_scale, 100)
            self.assertEqual(domain.distance_matrix[0][1], 125)
            self.assertEqual(domain.distance_matrix[1][0], 250)
            with redirect_stdout(io.StringIO()):
                solution = TSPSolver(0.1, 1).solve(CotwinBuilder().build_cotwin(domain))
            self.assertEqual(solution.tour_ids, (7, 9))
            self.assertEqual(solution.distance, 825)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "examples.or_tools.tsp_routing_model.scripts.solve_tsp",
                    "--input",
                    str(path),
                    "--no-improvement-seconds",
                    "0.1",
                    "--time-limit",
                    "1",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Solution distance (matrix units): 825", result.stdout)
            self.assertIn("Unique stops (excluding depot): 2", result.stdout)
            self.assertIn("Depot --> A --> B --> Depot", result.stdout)
            self.assertLess(
                result.stdout.index("New best solution #1:"),
                result.stdout.index("Solver status:"),
            )

    def test_checked_in_parser_preserves_source_matrix_rule(self):
        domain = DomainBuilder(DATASET).build_domain_from_scratch()
        self.assertEqual(len(domain.locations_list), 442)
        self.assertEqual(domain.vehicle.depot_id, 1)
        self.assertEqual(domain.distance_scale, 1000)
        left, right = domain.locations_list[:2]
        expected = round(
            1000
            * math.sqrt(
                (left.latitude - right.latitude) ** 2
                + (left.longitude - right.longitude) ** 2
            )
        )
        self.assertEqual(domain.distance_matrix[0][1], expected)
        self.assertEqual(domain.distance_matrix[1][0], expected)

    def test_reconstruction_rejects_incomplete_duplicate_and_wrong_distance(self):
        domain = small_domain()
        builder = DomainBuilder("unused")
        invalid = (
            (TSPSolution("ROUTING_SUCCESS", (7, 9), 1, 0, "test"), "omits"),
            (TSPSolution("ROUTING_SUCCESS", (7, 7, 9), 1, 0, "test"), "repeats"),
            (TSPSolution("ROUTING_SUCCESS", (7, 9, 100), 1, 0, "test"), "unknown"),
            (TSPSolution("ROUTING_SUCCESS", (7, 9, 11), 1, 0, "test"), "differs"),
            (
                TSPSolution("ROUTING_FAIL", None, None, 0, "test"),
                "without an incumbent",
            ),
        )
        for solution, message in invalid:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                builder.build_from_solution(solution, domain)
        self.assertIsNone(domain.vehicle.trip_path)

    def test_invalid_input_and_routing_integer_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.tsp"
            path.write_text(
                "NAME: bad\nTYPE: TSP\nDIMENSION: 3\n"
                "EDGE_WEIGHT_TYPE: EUC_2D\nNODE_COORD_SECTION\n"
                "1 0 0\n1 1 0\n2 0 1\nEOF\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unique"):
                DomainBuilder(path).build_domain_from_scratch()
        domain = small_domain()
        domain.distance_matrix[0][1] = 2**61
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder().build_cotwin(domain)

    def test_strict_improvement_logging_and_idle_limit(self):
        clock = [0.0]
        test_case = self

        class FakeRouting:
            def AddAtSolutionCallback(self, callback):
                self.on_solution = callback

            def solver(self):
                return self

            def CustomLimit(self, callback):
                self.idle_limit = callback
                return callback

            def AddSearchMonitor(self, _monitor):
                pass

            def CostVar(self):
                return self

            def Value(self):
                return self.distance

            def SolveWithParameters(self, _parameters):
                for now, distance in ((0, 20), (1, 20), (2, 19), (3, 21)):
                    clock[0] = now
                    self.distance = distance
                    self.on_solution()
                    test_case.assertFalse(self.idle_limit())
                clock[0] = 8
                test_case.assertTrue(self.idle_limit())
                return None

            def status(self):
                return 0

        cotwin = SimpleNamespace(routing=FakeRouting(), objective_bound=100)
        with (
            patch(
                "examples.or_tools.tsp_routing_model.solver.TSPSolver.monotonic",
                side_effect=lambda: clock[0],
            ),
            redirect_stdout(io.StringIO()) as output,
        ):
            solution = TSPSolver(5).solve(cotwin)
        self.assertEqual(solution.termination_reason, "no_improvement")
        self.assertFalse(solution.has_solution)
        scores = [
            int(value) for value in re.findall(r"distance=(\d+)", output.getvalue())
        ]
        self.assertEqual(scores, [20, 19])

    def test_invalid_termination_settings(self):
        for setting in (
            {"no_improvement_seconds": 0},
            {"no_improvement_seconds": float("nan")},
            {"time_limit": 0},
            {"time_limit": float("inf")},
            {"time_limit": 1_000_001},
        ):
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                TSPSolver(**setting)


if __name__ == "__main__":
    unittest.main()
