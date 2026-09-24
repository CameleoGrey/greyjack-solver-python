import io
import itertools
import math
import random
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from ortools.sat.python import cp_model

from examples.or_tools.facility_location.domain import (
    Consumer,
    Facility,
    FacilityLocationDomain,
    Location,
)
from examples.or_tools.facility_location.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.facility_location.persistence.DemoDataBuilder import (
    DemoDataBuilder,
)
from examples.or_tools.facility_location.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.facility_location.solver.FacilityLocationSolver import (
    FacilityLocationSolver,
)
from examples.or_tools.facility_location.solver.ScoreNoImprovement import (
    ScoreNoImprovement,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = PROJECT_ROOT / "examples/or_tools/facility_location/scripts/solve_task.py"


def independent_score(domain, assignment):
    """Exhaustive-search oracle without model expressions or domain methods."""
    hard = 0
    setup = 0
    distance = 0
    for facility in domain.facilities:
        assigned = [c for c in domain.consumers if assignment[c.id] == facility.id]
        hard += max(0, sum(c.demand for c in assigned) - facility.capacity)
        if assigned:
            setup += facility.setup_cost
        for consumer in assigned:
            latitude = consumer.location.latitude - facility.location.latitude
            longitude = consumer.location.longitude - facility.location.longitude
            distance += math.ceil(math.sqrt(latitude**2 + longitude**2) * 111_000)
    return hard, 2 * setup + 5 * distance


class FacilityLocationTests(unittest.TestCase):
    def solve(self, domain, mode="strict", hints=True):
        cotwin = CotwinBuilder(mode=mode, use_greedy_hints=hints).build_cotwin(domain)
        with redirect_stdout(io.StringIO()):
            return FacilityLocationSolver(
                workers=1, no_improvement_seconds=2, time_limit=5
            ).solve(cotwin)

    def test_small_optima_match_exhaustive_enumeration_in_both_modes(self):
        domains = [
            FacilityLocationDomain(
                [
                    Facility(41, Location(0, 0), 7, 2),
                    Facility(-8, Location(0, 0.01), 12, 2),
                ],
                [
                    Consumer(100, Location(0, 0), 2),
                    Consumer(-2, Location(0, 0.01), 2),
                ],
            ),
            FacilityLocationDomain(
                [
                    Facility(10, Location(0, 0), 100, 1),
                    Facility(20, Location(0, 0.001), 3, 2),
                    Facility(30, Location(0.001, 0), -5, 1),
                ],
                [
                    Consumer(9, Location(0, 0), 1),
                    Consumer(8, Location(0, 0.001), 1),
                    Consumer(7, Location(0.001, 0), 1),
                ],
            ),
        ]
        for domain in domains:
            candidates = [
                dict(zip((c.id for c in domain.consumers), facility_ids))
                for facility_ids in itertools.product(
                    (f.id for f in domain.facilities), repeat=len(domain.consumers)
                )
            ]
            for mode in ("strict", "penalized"):
                for hints in (False, True):
                    with self.subTest(domain=domain, mode=mode, hints=hints):
                        scores = [independent_score(domain, x) for x in candidates]
                        optimum = min(
                            score
                            for score in scores
                            if mode == "penalized" or score[0] == 0
                        )
                        result = self.solve(domain, mode, hints)
                        self.assertEqual(result.status, "OPTIMAL")
                        self.assertEqual(
                            (result.hard_penalty, result.soft_cost), optimum
                        )
                        self.assertEqual(
                            independent_score(domain, result.assignments), optimum
                        )
                        reconstructed = DomainBuilder().build_from_solution(
                            result, domain
                        )
                        self.assertEqual(
                            reconstructed.calculate_metrics()["soft_cost"], optimum[1]
                        )
                        self.assertTrue(
                            all(c.facility is None for c in domain.consumers)
                        )

    def test_active_source_weights_and_ceil_distance(self):
        domain = FacilityLocationDomain(
            [Facility(40, Location(0, 0), 10, 1)],
            [Consumer(900, Location(0, 0.001), 1)],
        )
        result = self.solve(domain)
        self.assertEqual((result.hard_penalty, result.soft_cost), (0, 575))
        solved = DomainBuilder().build_from_solution(result, domain)
        self.assertEqual(solved.calculate_metrics()["total_distance_m"], 111)
        self.assertEqual(solved.facilities[0].get_used_capacity(), 1)

    def test_strict_infeasibility_has_no_fallback(self):
        domain = FacilityLocationDomain(
            [Facility(5, Location(0, 0), 7, 0)],
            [Consumer(12, Location(0, 0), 1)],
        )
        strict = self.solve(domain, "strict")
        penalized = self.solve(domain, "penalized")
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)
        self.assertIsNone(strict.assignments)
        self.assertIsNone(strict.soft_cost)
        self.assertEqual((penalized.hard_penalty, penalized.soft_cost), (1, 14))
        self.assertTrue(penalized.has_solution)
        with self.assertRaises(ValueError):
            DomainBuilder().build_from_solution(strict, domain)

    def test_hard_score_precedes_arbitrarily_large_soft_savings(self):
        domain = FacilityLocationDomain(
            [
                Facility(1, Location(0, 0), 0, 0),
                Facility(2, Location(0, 0), 1_000_000, 1),
            ],
            [Consumer(3, Location(0, 0), 1)],
        )
        result = self.solve(domain, "penalized")
        self.assertEqual((result.hard_penalty, result.soft_cost), (0, 2_000_000))
        self.assertEqual(result.assignments, {3: 2})

    def test_zero_demand_still_activates_a_facility(self):
        domain = FacilityLocationDomain(
            [
                Facility(4, Location(0, 0), 10, 0),
                Facility(5, Location(0, 0), -5, 0),
            ],
            [Consumer(80, Location(0, 0), 0)],
        )
        cotwin = CotwinBuilder().build_cotwin(domain)
        solver = cp_model.CpSolver()
        self.assertEqual(solver.solve(cotwin.model), cp_model.OPTIMAL)
        self.assertEqual(solver.value(cotwin.facility_used[5]), 1)
        self.assertEqual(solver.value(cotwin.facility_used[4]), 0)
        self.assertEqual(solver.value(cotwin.soft_cost), -10)

    def test_consumer_assignment_updates_inverse_membership(self):
        first = Facility(1, Location(0, 0), 1, 10)
        second = Facility(2, Location(0, 0), 2, 10)
        consumer = Consumer(3, Location(0, 0), 4)
        consumer.facility = first
        self.assertEqual(first.get_used_capacity(), 4)
        self.assertTrue(first.is_used())
        consumer.facility = second
        self.assertFalse(first.is_used())
        self.assertEqual(second.consumers, [consumer])
        consumer.facility = None
        self.assertFalse(second.is_used())

    def test_partial_domain_helpers_match_source_behavior(self):
        facility = Facility(1, Location(0, 0), 9, 2)
        assigned = Consumer(2, Location(0, 0.01), 1, facility)
        unassigned = Consumer(3, Location(0, 0), 1)
        domain = FacilityLocationDomain([facility], [assigned, unassigned])
        self.assertEqual(domain.get_total_cost(), 9)
        self.assertEqual(domain.get_total_distance(), "1 km")
        with self.assertRaisesRegex(ValueError, "unassigned"):
            domain.calculate_metrics()

    def test_callback_reports_strict_improvements_only(self):
        clock = [10.0]
        callback = ScoreNoImprovement(None, None, None, 60, clock=lambda: clock[0])
        output = io.StringIO()
        with redirect_stdout(output):
            callback.start()
            try:
                callback.record_improvement((2, 10))
                callback.record_improvement((2, 10))
                callback.record_improvement((1, 100))
                callback.record_improvement((2, 0))
            finally:
                callback.close()
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("hard_penalty=2, soft_cost=10", lines[0])
        self.assertIn("hard_penalty=1, soft_cost=100", lines[1])

    def test_default_generator_is_deterministic_and_local(self):
        state = random.getstate()
        first = DomainBuilder().build_domain_from_scratch()
        second = DomainBuilder().build_domain_from_scratch()
        self.assertEqual(random.getstate(), state)
        self.assertEqual((len(first.facilities), len(first.consumers)), (30, 60))
        self.assertEqual(
            [f.setup_cost for f in first.facilities],
            [f.setup_cost for f in second.facilities],
        )
        self.assertEqual(first.facilities[0].setup_cost, 43_203)
        self.assertEqual(first.facilities[0].capacity, 150)
        self.assertEqual(first.consumers[0].demand, 15)
        self.assertEqual(
            [f.location for f in first.facilities],
            [f.location for f in second.facilities],
        )

    def test_custom_generator_keeps_source_integer_division(self):
        builder = (
            DemoDataBuilder.builder()
            .set_capacity(5)
            .set_demand(3)
            .set_facility_count(2)
            .set_consumer_count(2)
            .set_average_setup_cost(10)
            .set_setup_cost_standard_deviation(0)
            .set_south_west_corner(Location(0, 0))
            .set_north_east_corner(Location(1, 1))
        )
        domain = DomainBuilder(
            seed=7, demo_data_builder=builder
        ).build_domain_from_scratch()
        self.assertEqual([f.capacity for f in domain.facilities], [2, 2])
        self.assertEqual([c.demand for c in domain.consumers], [1, 1])

    def test_reconstruction_rejects_missing_unknown_and_score_mismatch(self):
        domain = FacilityLocationDomain(
            [Facility(9, Location(0, 0), 7, 1)],
            [Consumer(3, Location(0, 0), 1)],
        )
        result = self.solve(domain)
        original = deepcopy(domain)
        for broken in (
            replace(result, assignments={}),
            replace(result, assignments={3: 999}),
            replace(result, hard_penalty=1),
            replace(result, soft_cost=0),
            replace(result, status="UNKNOWN", assignments=None),
        ):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                DomainBuilder().build_from_solution(broken, domain)
        self.assertEqual(
            domain.facilities[0].consumers, original.facilities[0].consumers
        )
        self.assertIsNone(domain.consumers[0].facility)

    def test_empty_domain_and_validation(self):
        empty = FacilityLocationDomain.empty()
        result = self.solve(empty)
        self.assertEqual((result.hard_penalty, result.soft_cost), (0, 0))
        self.assertEqual(result.assignments, {})
        self.assertEqual(empty.calculate_metrics()["facilities_used"], 0)
        invalid = [
            FacilityLocationDomain([], [Consumer(1, Location(0, 0), 1)]),
            FacilityLocationDomain(
                [Facility(1, Location(0, 0), 1, 1), Facility(1, Location(0, 0), 1, 1)],
                [],
            ),
            FacilityLocationDomain(
                [Facility(1, Location(0, 0), 1, 1)], [Consumer(2, Location(0, 0), -1)]
            ),
            FacilityLocationDomain([Facility(1, Location(float("nan"), 0), 1, 1)], []),
        ]
        for domain in invalid:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                CotwinBuilder().build_cotwin(domain)

    def test_mode_specific_integer_bounds(self):
        domain = FacilityLocationDomain(
            [Facility(1, Location(0, 0), 2**60, 1)],
            [Consumer(2, Location(0, 0), 1)],
        )
        strict = CotwinBuilder(mode="strict").build_cotwin(domain)
        self.assertEqual(strict.hard_weight, 0)
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder(mode="penalized").build_cotwin(domain)
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="wrong")

    def test_cli_direct_and_module_help(self):
        direct = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workers",
                "1",
                "--time-limit",
                "2",
                "--no-improvement-seconds",
                "2",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertIn("Mode: strict", direct.stdout)
        self.assertIn("Capacity feasible: True", direct.stdout)
        self.assertIn("Hard penalty (total overload): 0", direct.stdout)
        module = subprocess.run(
            [
                sys.executable,
                "-m",
                "examples.or_tools.facility_location.scripts.solve_task",
                "--help",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(module.returncode, 0, module.stderr)
        self.assertIn("--mode", module.stdout)


if __name__ == "__main__":
    unittest.main()
