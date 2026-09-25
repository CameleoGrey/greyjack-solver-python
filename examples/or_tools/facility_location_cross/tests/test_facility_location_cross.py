import io
import itertools
import math
import random
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

from examples.or_tools.facility_location_cross.domain import (
    Consumer,
    Facility,
    FacilityLocationDomain,
    Location,
)
from examples.or_tools.facility_location_cross.persistence.CotwinBuilder import (
    CotwinBuilder,
)
from examples.or_tools.facility_location_cross.persistence.DomainBuilder import (
    DomainBuilder,
)
from examples.or_tools.facility_location_cross.solver.DualMaster import (
    DualMaster,
    Pattern,
)
from examples.or_tools.facility_location_cross.solver.ExactClosure import ExactClosure
from examples.or_tools.facility_location_cross.solver.FacilityLocationSolver import (
    FacilityLocationSolver,
)
from examples.or_tools.facility_location_cross.solver.FixedOpeningSubproblem import (
    FixedOpeningSubproblem,
)
from examples.or_tools.facility_location_cross.solver.PricedSubproblem import (
    PriceVector,
    PricedSubproblem,
    PricingResult,
)
from examples.or_tools.facility_location_cross.solver.ScoreNoImprovement import (
    ScoreNoImprovement,
)


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "examples/or_tools/facility_location_cross/scripts/solve_task.py"


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


class FacilityLocationCrossTests(unittest.TestCase):
    def solve(self, domain, mode="strict", seed=True, seconds=5):
        cotwin = CotwinBuilder(mode=mode, use_greedy_seed=seed).build_cotwin(domain)
        with redirect_stdout(io.StringIO()):
            result = FacilityLocationSolver(
                workers=1, no_improvement_seconds=seconds, time_limit=seconds
            ).solve(cotwin)
        return result

    def test_small_optima_match_exhaustive_oracle(self):
        domains = [
            FacilityLocationDomain(
                [
                    Facility(41, Location(0, 0), 7, 2),
                    Facility(-8, Location(0, 0.01), 12, 2),
                ],
                [Consumer(100, Location(0, 0), 2), Consumer(-2, Location(0, 0.01), 2)],
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
                [Consumer(3, Location(0, 0), 0), Consumer(4, Location(0, 0), 0)],
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
                        self.assertEqual(
                            result.lower_bound,
                            result.soft_cost
                            + CotwinBuilder(mode=mode).build_cotwin(domain).hard_weight
                            * result.hard_penalty,
                        )
                        solved = DomainBuilder().build_from_solution(result, domain)
                        self.assertEqual(
                            solved.calculate_metrics()["soft_cost"], optimum[1]
                        )
                        self.assertTrue(
                            all(c.facility is None for c in domain.consumers)
                        )

    def test_strict_infeasible_and_penalized_hard_first(self):
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

    def test_fractional_fixed_opening_lp_uses_exact_recourse(self):
        domain = FacilityLocationDomain(
            [Facility(fid, Location(0, 0), 1, 3) for fid in (1, 2, 3)],
            [Consumer(cid, Location(0, 0), 2) for cid in (10, 20, 30)],
        )
        cotwin = CotwinBuilder(use_greedy_seed=False).build_cotwin(domain)
        lp = FixedOpeningSubproblem(cotwin).solve_lp({1, 2}, 2)
        self.assertEqual(lp.status, pywraplp.Solver.OPTIMAL)
        self.assertIsNone(lp.assignments)
        result = self.solve(domain, seed=False)
        self.assertEqual(result.status, "OPTIMAL")
        self.assertEqual(result.hard_penalty, 0)
        self.assertEqual(set(result.assignments.values()), {1, 2, 3})
        self.assertGreater(result.dual_master_solves, 0)

    def test_fixed_opening_dual_cut_bounds_all_opening_patterns(self):
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
        patterns = [
            set(ids)
            for count in range(4)
            for ids in itertools.combinations((1, 2, 3), count)
        ]
        for mode in ("strict", "penalized"):
            cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
            fixed = FixedOpeningSubproblem(cotwin)
            for source in patterns:
                cut = fixed.solve_lp(source, 2).cut
                if cut is None:
                    continue
                for target in patterns:
                    recourse = []
                    for assignment in oracle_assignments(domain):
                        if set(assignment.values()) != target:
                            continue
                        hard, soft = oracle_score(domain, assignment)
                        if mode == "strict" and hard:
                            continue
                        setup = 2 * sum(
                            f.setup_cost for f in domain.facilities if f.id in target
                        )
                        recourse.append(cotwin.hard_weight * hard + soft - setup)
                    if recourse:
                        self.assertLessEqual(cut.value(target), min(recourse))

    def test_priced_lower_bound_and_dual_master_phases(self):
        domain = FacilityLocationDomain(
            [Facility(1, Location(0, 0), -2, 1), Facility(2, Location(0, 0.001), 3, 1)],
            [Consumer(10, Location(0, 0), 1), Consumer(20, Location(0, 0.001), 1)],
        )
        cotwin = CotwinBuilder().build_cotwin(domain)
        master = DualMaster(cotwin)
        self.assertTrue(master.add_pattern({10: 1, 20: 1}))
        first = master.solve(1)
        self.assertEqual(first.phase, "feasibility")
        self.assertGreater(first.value, 0)
        self.assertTrue(master.add_pattern({10: 1, 20: 2}))
        second = master.solve(1)
        self.assertEqual(second.phase, "cost")
        self.assertEqual(len(master.patterns), 2)

        priced = PricedSubproblem(cotwin)
        prices = priced.checked_prices({1: Fraction(3, 2), 2: Fraction(1, 3)})
        result = priced.solve(prices, "cost", 2, 1, lambda _: None)
        self.assertEqual(result.status, cp_model.OPTIMAL)
        candidates = []
        for assignment in oracle_assignments(domain):
            pattern = Pattern.from_assignment(cotwin, assignment)
            candidates.append(
                pattern.base_cost
                + sum(
                    prices.fractions()[fid] * residual
                    for fid, residual in pattern.residuals
                )
            )
        self.assertEqual(result.lower_bound, min(candidates))
        self.assertLessEqual(
            result.lower_bound,
            min(
                oracle_score(domain, a)[1]
                for a in oracle_assignments(domain)
                if oracle_score(domain, a)[0] == 0
            ),
        )

        penalized = CotwinBuilder(mode="penalized").build_cotwin(domain)
        penalized_pricer = PricedSubproblem(penalized)
        penalized_prices = penalized_pricer.checked_prices(
            {1: penalized.hard_weight, 2: Fraction(1, 3)}
        )
        penalized_result = penalized_pricer.solve(
            penalized_prices, "cost", 2, 1, lambda _: None
        )
        optimum = min(
            penalized.hard_weight * oracle_score(domain, a)[0]
            + oracle_score(domain, a)[1]
            for a in oracle_assignments(domain)
        )
        self.assertEqual(penalized_result.status, cp_model.OPTIMAL)
        self.assertLessEqual(penalized_result.lower_bound, optimum)

        restricted = DualMaster(penalized)
        restricted.add_pattern({10: 1, 20: 1})
        self.assertGreater(restricted.solve(1).value, optimum)

    def test_reconstruction_rejects_corrupt_results(self):
        domain = FacilityLocationDomain(
            [Facility(9, Location(0, 0), 7, 1)], [Consumer(3, Location(0, 0), 1)]
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

    def test_logger_and_unresolved_statuses(self):
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
        self.assertEqual(len(output.getvalue().splitlines()), 2)

        domain = FacilityLocationDomain(
            [Facility(1, Location(0, 0), 7, 1)], [Consumer(2, Location(0, 0), 1)]
        )
        with (
            patch.object(
                PricedSubproblem,
                "solve",
                return_value=PricingResult(
                    cp_model.UNKNOWN, None, None, PriceVector(1, {1: 0}), "cost"
                ),
            ),
            patch.object(ExactClosure, "solve", return_value=(cp_model.UNKNOWN, None)),
        ):
            self.assertEqual(
                self.solve(domain, seed=False, seconds=0.05).status, "UNKNOWN"
            )
            self.assertEqual(
                self.solve(domain, seed=True, seconds=0.05).status, "FEASIBLE"
            )

    def test_unavailable_pricing_uses_exact_closure(self):
        domain = FacilityLocationDomain(
            [Facility(1, Location(0, 0), 7, 1)],
            [Consumer(2, Location(0, 0), 1)],
        )
        with patch.object(PricedSubproblem, "checked_prices", side_effect=ValueError):
            result = self.solve(domain, seed=False)
        self.assertEqual(result.status, "OPTIMAL")
        self.assertEqual((result.hard_penalty, result.soft_cost), (0, 14))
        self.assertEqual(result.pricing_solves, 0)

    def test_generator_bounds_and_cli(self):
        state = random.getstate()
        domain = DomainBuilder().build_domain_from_scratch()
        self.assertEqual(random.getstate(), state)
        self.assertEqual((len(domain.facilities), len(domain.consumers)), (30, 60))
        self.assertEqual(domain.facilities[0].setup_cost, 43_203)
        self.assertEqual(domain.consumers[0].demand, 15)
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="wrong")
        with self.assertRaises(ValueError):
            CotwinBuilder().build_cotwin(
                FacilityLocationDomain([], [Consumer(1, Location(0, 0), 1)])
            )

        high_cost = FacilityLocationDomain(
            [Facility(1, Location(0, 0), 2**60, 1)],
            [Consumer(2, Location(0, 0), 1)],
        )
        self.assertEqual(self.solve(high_cost).soft_cost, 2**61)
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder(mode="penalized").build_cotwin(high_cost)

        direct = subprocess.run(
            [sys.executable, str(SCRIPT), "--workers", "1", "--time-limit", "1"],
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
                "examples.or_tools.facility_location_cross.scripts.solve_task",
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
