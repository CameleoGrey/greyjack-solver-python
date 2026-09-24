import io
import itertools
import math
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from ortools.sat.python import cp_model

from examples.or_tools.tsp_cp_sat.domain import Location, TravelSchedule, Vehicle
from examples.or_tools.tsp_cp_sat.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.tsp_cp_sat.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.tsp_cp_sat.solver.ScoreNoImprovement import ScoreNoImprovement
from examples.or_tools.tsp_cp_sat.solver.TSPSolution import TSPSolution
from examples.or_tools.tsp_cp_sat.solver.TSPSolver import TSPSolver


ROOT = Path(__file__).resolve().parents[4]
DATASET = ROOT / "data/tsp/belgium-n50.tsp"


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


class TSPTests(unittest.TestCase):
    def test_optimum_matches_exhaustive_directed_tours_and_replay(self):
        domain = small_domain()
        expected = best_distance_by_enumeration(domain)
        for formulation in ("mtz", "circuit"):
            for hints in (False, True):
                with self.subTest(formulation=formulation, hints=hints):
                    cotwin = CotwinBuilder(
                        use_greedy_hints=hints, formulation=formulation
                    ).build_cotwin(domain)
                    self.assertEqual(bool(cotwin.order), formulation == "mtz")
                    self.assertEqual(
                        sum(
                            constraint.has_circuit()
                            for constraint in cotwin.model.proto.constraints
                        ),
                        1 if formulation == "circuit" else 0,
                    )
                    solution = TSPSolver(workers=1, time_limit=5).solve(cotwin)
                    self.assertEqual(solution.status, "OPTIMAL")
                    self.assertEqual(solution.distance, expected)
                    self.assertEqual(set(solution.tour_ids), {7, 9, 11})
                    solved = DomainBuilder("unused").build_from_solution(
                        solution, domain
                    )
                    self.assertEqual(solved.calculate_metrics()["distance"], expected)
                    self.assertIsNone(domain.vehicle.trip_path)
                    self.assertEqual(
                        solved.vehicle.trip_path[0],
                        solved.location_by_id[solution.tour_ids[0]],
                    )

    def test_formulations_exclude_disconnected_customer_cycle(self):
        matrix = [[0, 100, 100, 100]] + [
            [100, *[0 for _ in range(3)]] for _ in range(3)
        ]
        for formulation in ("mtz", "circuit"):
            with self.subTest(formulation=formulation):
                solution = TSPSolver(workers=1, time_limit=5).solve(
                    CotwinBuilder(
                        use_greedy_hints=False, formulation=formulation
                    ).build_cotwin(small_domain(matrix))
                )
                self.assertEqual(solution.status, "OPTIMAL")
                self.assertEqual(solution.distance, 200)
                self.assertEqual(set(solution.tour_ids), {7, 9, 11})

    def test_two_location_tour_in_both_formulations(self):
        domain = small_domain()
        domain.locations_list = domain.locations_list[:2]
        domain.distance_matrix = [row[:2] for row in domain.distance_matrix[:2]]
        for formulation in ("mtz", "circuit"):
            with self.subTest(formulation=formulation):
                solution = TSPSolver(workers=1, time_limit=5).solve(
                    CotwinBuilder(formulation=formulation).build_cotwin(domain)
                )
                self.assertEqual(solution.status, "OPTIMAL")
                self.assertEqual(solution.tour_ids, (7,))
                self.assertEqual(solution.distance, 10)

    def test_real_input_preserves_ids_names_and_source_distance_rule(self):
        domain = DomainBuilder(DATASET).build_domain_from_scratch()
        self.assertEqual(len(domain.locations_list), 50)
        self.assertEqual(domain.vehicle.depot_id, 0)
        self.assertEqual(domain.locations_list[1].id, 55)
        self.assertEqual(domain.locations_list[1].name, "ANTHISNES")
        self.assertEqual(domain.distance_scale, 1000)
        left, right = domain.locations_list[:2]
        source_distance = round(
            1000
            * math.sqrt(
                (left.latitude - right.latitude) ** 2
                + (left.longitude - right.longitude) ** 2
            )
        )
        self.assertEqual(domain.distance_matrix[0][1], source_distance)
        self.assertEqual(domain.distance_matrix[1][0], source_distance)

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
            builder = DomainBuilder(path)
            domain = builder.build_domain_from_scratch()
            self.assertEqual(domain.distance_scale, 100)
            self.assertEqual(domain.distance_matrix[0][1], 125)
            self.assertEqual(domain.distance_matrix[1][0], 250)
            solution = TSPSolver(workers=1, time_limit=5).solve(
                CotwinBuilder().build_cotwin(domain)
            )
            self.assertEqual(solution.status, "OPTIMAL")
            self.assertEqual(solution.tour_ids, (7, 9))
            self.assertEqual(solution.distance, 825)
            for formulation in (None, "mtz", "circuit"):
                with self.subTest(formulation=formulation):
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "examples.or_tools.tsp_cp_sat.scripts.solve_tsp",
                            "--input",
                            str(path),
                            "--workers",
                            "1",
                            "--no-improvement-seconds",
                            "1",
                            "--time-limit",
                            "5",
                            *(["--formulation", formulation] if formulation else []),
                        ],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(
                        f"Building {(formulation or 'mtz').upper()} model:",
                        result.stdout,
                    )
                    score_lines = re.findall(
                        r"New best solution #(\d+): distance=(\d+)", result.stdout
                    )
                    self.assertTrue(score_lines, result.stdout)
                    self.assertEqual(
                        [int(sequence) for sequence, _ in score_lines],
                        list(range(1, len(score_lines) + 1)),
                    )
                    distances = [int(distance) for _, distance in score_lines]
                    self.assertTrue(
                        all(
                            previous > current
                            for previous, current in zip(distances, distances[1:])
                        )
                    )
                    self.assertEqual(score_lines[-1][1], "825")
                    self.assertLess(
                        result.stdout.index("New best solution #1:"),
                        result.stdout.index("Solver status:"),
                    )
                    self.assertIn(
                        "Solution distance (matrix units): 825", result.stdout
                    )
                    self.assertIn("Unique stops (excluding depot): 2", result.stdout)

    def test_invalid_formulation(self):
        with self.assertRaisesRegex(ValueError, "formulation"):
            CotwinBuilder(formulation="unknown")

    def test_reconstruction_rejects_invalid_or_mismatched_tours(self):
        domain = small_domain()
        builder = DomainBuilder("unused")
        invalid = (
            (TSPSolution("FEASIBLE", (7, 9), 1, 0, "test"), "omits"),
            (TSPSolution("FEASIBLE", (7, 7, 9), 1, 0, "test"), "repeats"),
            (TSPSolution("FEASIBLE", (7, 9, 100), 1, 0, "test"), "unknown"),
            (TSPSolution("FEASIBLE", (7, 9, 11), 1, 0, "test"), "differs"),
            (TSPSolution("UNKNOWN", None, None, 0, "test"), "without an incumbent"),
        )
        for solution, message in invalid:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                builder.build_from_solution(solution, domain)
        self.assertIsNone(domain.vehicle.trip_path)

    def test_invalid_input_and_integer_bounds(self):
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

    def test_idle_deadline_resets_only_for_strict_improvements(self):
        stopped = threading.Event()
        solver = Mock()
        solver.stop_search.side_effect = stopped.set
        clock = [0.0]
        monitor = ScoreNoImprovement(solver, None, 15, clock=lambda: clock[0])
        monitor.start()
        try:
            with redirect_stdout(io.StringIO()) as output:
                monitor.record_improvement(2**53 + 4)
                clock[0] = 10
                monitor.record_improvement(2**53 + 3)
                clock[0] = 16
                self.assertFalse(stopped.wait(0.15))
                monitor.record_improvement(2**53 + 3)
                monitor.record_improvement(2**53 + 5)
                clock[0] = 26
                self.assertTrue(stopped.wait(2))
            self.assertTrue(monitor.timed_out)
            self.assertEqual(output.getvalue().count("New best solution"), 2)
        finally:
            monitor.close()
        self.assertFalse(
            any(thread.name == "tsp-idle-watchdog" for thread in threading.enumerate())
        )

    def test_idle_timeout_without_callbacks_reports_no_incumbent(self):
        cotwin = CotwinBuilder().build_cotwin(small_domain())
        stopped = threading.Event()
        with patch(
            "examples.or_tools.tsp_cp_sat.solver.TSPSolver.cp_model.CpSolver"
        ) as factory:
            solver = factory.return_value
            solver.stop_search.side_effect = stopped.set

            def solve_without_callbacks(*_args):
                self.assertTrue(stopped.wait(2))
                return cp_model.UNKNOWN

            solver.solve.side_effect = solve_without_callbacks
            solver.status_name.return_value = "UNKNOWN"
            result = TSPSolver(no_improvement_seconds=0.01).solve(cotwin)
            self.assertEqual(result.termination_reason, "no_improvement")
            self.assertFalse(result.has_solution)
            solver.value.assert_not_called()
        self.assertFalse(
            any(thread.name == "tsp-idle-watchdog" for thread in threading.enumerate())
        )

    def test_invalid_termination_settings(self):
        for setting in (
            {"no_improvement_seconds": 0},
            {"no_improvement_seconds": float("nan")},
            {"time_limit": 0},
            {"time_limit": float("inf")},
        ):
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                TSPSolver(**setting)


if __name__ == "__main__":
    unittest.main()
