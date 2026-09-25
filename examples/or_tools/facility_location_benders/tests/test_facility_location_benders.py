import io
import itertools
import math
import random
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

from examples.or_tools.facility_location_benders.domain import (
    Consumer,
    Facility,
    FacilityLocationDomain,
    Location,
)
from examples.or_tools.facility_location_benders.persistence.CotwinBuilder import (
    CotwinBuilder,
)
from examples.or_tools.facility_location_benders.persistence.DomainBuilder import (
    DomainBuilder,
)
from examples.or_tools.facility_location_benders.solver.AssignmentSubproblem import (
    AssignmentLPResult,
    AssignmentSubproblem,
)
from examples.or_tools.facility_location_benders.solver.FacilityLocationSolver import (
    FacilityLocationSolver,
)
from examples.or_tools.facility_location_benders.solver.ScoreNoImprovement import (
    ScoreNoImprovement,
)


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "examples/or_tools/facility_location_benders/scripts/solve_task.py"


def oracle_score(domain, assignment):
    hard = 0
    setup = 0
    distance = 0
    for facility in domain.facilities:
        selected = [c for c in domain.consumers if assignment[c.id] == facility.id]
        hard += max(0, sum(c.demand for c in selected) - facility.capacity)
        if selected:
            setup += facility.setup_cost
        for consumer in selected:
            lat = consumer.location.latitude - facility.location.latitude
            lon = consumer.location.longitude - facility.location.longitude
            distance += math.ceil(math.sqrt(lat * lat + lon * lon) * 111_000)
    return hard, 2 * setup + 5 * distance


def oracle_assignments(domain):
    if not domain.consumers:
        yield {}
        return
    for choices in itertools.product(
        (facility.id for facility in domain.facilities), repeat=len(domain.consumers)
    ):
        yield dict(zip((consumer.id for consumer in domain.consumers), choices))


class FacilityLocationBendersTests(unittest.TestCase):
    def solve(self, domain, mode="strict", seed=True):
        cotwin = CotwinBuilder(mode=mode, use_greedy_seed=seed).build_cotwin(domain)
        with redirect_stdout(io.StringIO()):
            result = FacilityLocationSolver(
                workers=1, no_improvement_seconds=10, time_limit=10
            ).solve(cotwin)
        return result

    def test_small_optima_match_exhaustive_oracle(self):
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
            FacilityLocationDomain(
                [
                    Facility(-10, Location(0, 0), -4, 3),
                    Facility(90, Location(0, 0.002), -7, 2),
                    Facility(7, Location(0, 0.001), 2, 0),
                ],
                [
                    Consumer(99, Location(0, 0), 3),
                    Consumer(1, Location(0, 0.002), 2),
                    Consumer(-4, Location(0, 0.001), 0),
                ],
            ),
            FacilityLocationDomain(
                [
                    Facility(1, Location(0, 0), -5, 0),
                    Facility(2, Location(0, 0), -3, 0),
                ],
                [
                    Consumer(3, Location(0, 0), 0),
                    Consumer(4, Location(0, 0), 0),
                ],
            ),
            FacilityLocationDomain([Facility(1, Location(0, 0), -5, 0)], []),
            FacilityLocationDomain.empty(),
        ]
        for domain in domains:
            for mode in ("strict", "penalized"):
                for seed in (False, True):
                    with self.subTest(domain=domain, mode=mode, seed=seed):
                        scores = [
                            oracle_score(domain, assignment)
                            for assignment in oracle_assignments(domain)
                        ]
                        optimum = min(
                            score
                            for score in scores
                            if mode == "penalized" or score[0] == 0
                        )
                        result = self.solve(domain, mode, seed)
                        self.assertEqual(result.status, "OPTIMAL", result)
                        self.assertEqual(
                            (result.hard_penalty, result.soft_cost), optimum
                        )
                        self.assertEqual(
                            oracle_score(domain, result.assignments), optimum
                        )
                        solved = DomainBuilder().build_from_solution(result, domain)
                        self.assertEqual(
                            solved.calculate_metrics()["soft_cost"], optimum[1]
                        )
                        self.assertTrue(
                            all(c.facility is None for c in domain.consumers)
                        )

    def test_strict_infeasible_and_penalized_lexicographic_score(self):
        impossible = FacilityLocationDomain(
            [Facility(5, Location(0, 0), 7, 0)],
            [Consumer(12, Location(0, 0), 1)],
        )
        strict = self.solve(impossible)
        self.assertEqual(
            (strict.status, strict.termination_reason), ("INFEASIBLE", "infeasible")
        )
        self.assertFalse(strict.has_solution)
        penalized = self.solve(impossible, "penalized")
        self.assertEqual((penalized.hard_penalty, penalized.soft_cost), (1, 14))

        hard_first = FacilityLocationDomain(
            [
                Facility(1, Location(0, 0), 0, 0),
                Facility(2, Location(0, 0), 1_000_000, 1),
            ],
            [Consumer(3, Location(0, 0), 1)],
        )
        result = self.solve(hard_first, "penalized")
        self.assertEqual((result.hard_penalty, result.soft_cost), (0, 2_000_000))
        self.assertEqual(result.assignments, {3: 2})

    def test_fractional_lp_requires_exact_integer_recourse(self):
        domain = FacilityLocationDomain(
            [Facility(fid, Location(0, 0), 1, 3) for fid in (1, 2, 3)],
            [Consumer(cid, Location(0, 0), 2) for cid in (10, 20, 30)],
        )
        cotwin = CotwinBuilder(use_greedy_seed=False).build_cotwin(domain)
        lp = AssignmentSubproblem(cotwin).solve({1, 2}, 2)
        self.assertEqual(lp.status, pywraplp.Solver.OPTIMAL)
        self.assertIsNone(lp.assignments)
        with redirect_stdout(io.StringIO()):
            result = FacilityLocationSolver(
                workers=1, no_improvement_seconds=10, time_limit=10
            ).solve(cotwin)
        self.assertEqual(result.status, "OPTIMAL")
        self.assertEqual(result.hard_penalty, 0)
        self.assertEqual(set(result.assignments.values()), {1, 2, 3})

        impossible = FacilityLocationDomain(domain.facilities[:2], domain.consumers)
        infeasible = self.solve(impossible, seed=False)
        self.assertEqual(infeasible.status, "INFEASIBLE")
        self.assertGreater(infeasible.feasibility_cuts, 0)

    def test_dual_cuts_bound_every_feasible_opening_pattern(self):
        domain = FacilityLocationDomain(
            [
                Facility(1, Location(0, 0), -2, 2),
                Facility(2, Location(0, 0.001), 3, 3),
                Facility(3, Location(0.001, 0), 5, 1),
            ],
            [
                Consumer(4, Location(0, 0), 2),
                Consumer(5, Location(0, 0.001), 1),
                Consumer(6, Location(0.001, 0), 0),
            ],
        )
        for mode in ("strict", "penalized"):
            cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
            patterns = [
                set(ids)
                for count in range(4)
                for ids in itertools.combinations((1, 2, 3), count)
            ]
            for source in patterns:
                cut = AssignmentSubproblem(cotwin).solve(source, 2).cut
                if cut is None:
                    continue
                for target in patterns:
                    feasible = []
                    for assignment in oracle_assignments(domain):
                        if set(assignment.values()) != target:
                            continue
                        hard, soft = oracle_score(domain, assignment)
                        if mode == "strict" and hard:
                            continue
                        setup = 2 * sum(
                            f.setup_cost for f in domain.facilities if f.id in target
                        )
                        feasible.append(cotwin.hard_weight * hard + soft - setup)
                    if feasible:
                        self.assertLessEqual(cut.value(target), min(feasible))

    def test_reconstruction_rejects_corrupt_results(self):
        domain = FacilityLocationDomain(
            [Facility(9, Location(0, 0), 7, 1)],
            [Consumer(3, Location(0, 0), 1)],
        )
        result = self.solve(domain)
        for broken in (
            replace(result, assignments={}),
            replace(result, assignments={3: 999}),
            replace(result, hard_penalty=1),
            replace(result, soft_cost=0),
            replace(result, status="UNKNOWN", assignments=None),
        ):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                DomainBuilder().build_from_solution(broken, domain)

    def test_logger_prints_only_strict_improvements_and_resets_idle_clock(self):
        clock = [10.0]
        logger = ScoreNoImprovement(10.0, 5, clock=lambda: clock[0])
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertTrue(logger.record((2, 10), {1: 2}))
            clock[0] = 11.0
            self.assertFalse(logger.record((2, 10), {1: 3}))
            self.assertEqual(logger.deadline, 15.0)
            self.assertTrue(logger.record((1, 100), {1: 3}))
            self.assertFalse(logger.record((2, 0), {1: 2}))
        self.assertEqual(logger.deadline, 16.0)
        self.assertEqual(logger.best_assignments, {1: 3})
        self.assertEqual(len(output.getvalue().splitlines()), 2)

    def test_unresolved_subproblem_never_claims_a_proof(self):
        domain = FacilityLocationDomain(
            [Facility(1, Location(0, 0), 7, 1)],
            [Consumer(2, Location(0, 0.001), 1)],
        )
        with (
            patch.object(
                AssignmentSubproblem,
                "solve",
                return_value=AssignmentLPResult(pywraplp.Solver.NOT_SOLVED, None, None),
            ),
            patch.object(
                FacilityLocationSolver,
                "_solve_integer",
                return_value=(cp_model.FEASIBLE, None, None),
            ),
        ):
            for seed, status in ((False, "UNKNOWN"), (True, "FEASIBLE")):
                with self.subTest(seed=seed):
                    result = self.solve(domain, seed=seed)
                    self.assertEqual(result.status, status)
                    self.assertEqual(result.termination_reason, "subproblem_unresolved")

    def test_generator_validation_and_global_rng(self):
        state = random.getstate()
        domain = DomainBuilder().build_domain_from_scratch()
        self.assertEqual(random.getstate(), state)
        self.assertEqual((len(domain.facilities), len(domain.consumers)), (30, 60))
        self.assertEqual(domain.facilities[0].setup_cost, 43_203)
        self.assertEqual(domain.facilities[0].capacity, 150)
        self.assertEqual(domain.consumers[0].demand, 15)
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="wrong")
        with self.assertRaises(ValueError):
            CotwinBuilder().build_cotwin(
                FacilityLocationDomain([], [Consumer(1, Location(0, 0), 1)])
            )

    def test_integer_bounds_match_source_modes(self):
        domain = FacilityLocationDomain(
            [Facility(1, Location(0, 0), 2**60, 1)],
            [Consumer(2, Location(0, 0), 1)],
        )
        self.assertEqual(self.solve(domain).soft_cost, 2**61)
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder(mode="penalized").build_cotwin(domain)

    def test_cli_direct_and_module_help(self):
        direct = subprocess.run(
            [sys.executable, str(SCRIPT), "--workers", "1", "--time-limit", "2"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertIn("Mode: strict", direct.stdout)
        self.assertIn("Capacity feasible: True", direct.stdout)
        module = subprocess.run(
            [
                sys.executable,
                "-m",
                "examples.or_tools.facility_location_benders.scripts.solve_task",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(module.returncode, 0, module.stderr)
        self.assertIn("--no-improvement-seconds", module.stdout)


if __name__ == "__main__":
    unittest.main()
