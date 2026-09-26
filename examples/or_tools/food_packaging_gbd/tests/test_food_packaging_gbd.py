import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from itertools import permutations
from pathlib import Path
from time import sleep

from examples.or_tools.food_packaging.persistence.CotwinBuilder import (
    CotwinBuilder as SourceCotwinBuilder,
)
from examples.or_tools.food_packaging.solver.FoodPackagingSolver import (
    FoodPackagingSolver as SourceFoodPackagingSolver,
)

from examples.or_tools.food_packaging_gbd.domain import (
    Job,
    Line,
    PackagingSchedule,
    Product,
)
from examples.or_tools.food_packaging_gbd.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.food_packaging_gbd.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.food_packaging_gbd.solver.FoodPackagingSolver import (
    FoodPackagingSolver,
)
from examples.or_tools.food_packaging_gbd.solver.ScoreNoImprovement import (
    ScoreNoImprovement,
)
from examples.or_tools.food_packaging_gbd.solver.TimingSubproblem import (
    convex_cut,
    earliest_schedule,
)


BASE = datetime(2026, 9, 28)
ROOT = Path(__file__).resolve().parents[4]


def schedule(*, shared_operator=False, tight_deadline=False):
    product = Product(10, "P")
    product.cleaning_durations[product] = timedelta(minutes=0)
    lines = [
        Line(20, "A", "shared", BASE),
        Line(23, "B", "shared" if shared_operator else "other", BASE),
    ]
    deadline = 5 if tight_deadline else 100
    jobs = [
        Job(
            jid,
            str(jid),
            product,
            timedelta(minutes=5),
            BASE,
            BASE + timedelta(minutes=20),
            BASE + timedelta(minutes=deadline),
        )
        for jid in (2, 7)
    ]
    return PackagingSchedule([product], lines, jobs)


class FoodPackagingGBDTests(unittest.TestCase):
    def solve(self, domain, mode="strict", seconds=5):
        cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
        output = io.StringIO()
        with redirect_stdout(output):
            result = FoodPackagingSolver(workers=1, time_limit=seconds).solve(cotwin)
        return cotwin, result, output.getvalue()

    def test_strict_and_penalized_shared_operator(self):
        domain = schedule(shared_operator=True)
        for mode in ("strict", "penalized"):
            with self.subTest(mode=mode):
                cotwin, result, output = self.solve(domain, mode)
                self.assertEqual(result.status, "OPTIMAL")
                self.assertGreater(result.gbd_cuts, 0)
                self.assertIn("New best solution #1", output)
                replay = DomainBuilder().build_from_solution(
                    result, initial_domain=domain
                )
                metrics = replay.calculate_metrics()
                self.assertEqual(
                    (result.hard_penalty, result.medium_penalty, result.soft_penalty),
                    (
                        metrics["hard_penalty"],
                        metrics["medium_penalty"],
                        metrics["soft_penalty"],
                    ),
                )
                self.assertTrue(mode != "strict" or metrics["strict_feasible"])
                self.assertEqual(set(result.start_times), set(cotwin.job_ids))
        self.assertEqual([job.start_time for job in domain.jobs], [None, None])

    def test_strict_infeasible_penalized_exact(self):
        domain = schedule(shared_operator=True, tight_deadline=True)
        _, strict, _ = self.solve(domain, "strict")
        _, penalized, _ = self.solve(domain, "penalized")
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)
        self.assertEqual(penalized.status, "OPTIMAL")
        self.assertEqual(penalized.hard_penalty, 0)
        self.assertGreater(penalized.soft_penalty, 0)

    def test_empty_and_one_late_job(self):
        _, empty, _ = self.solve(PackagingSchedule())
        self.assertEqual(empty.status, "OPTIMAL")
        self.assertEqual(empty.line_routes, {})
        domain = schedule()
        domain.lines.pop()
        domain.jobs.pop()
        domain.jobs[0].max_end_time = BASE + timedelta(minutes=2)
        _, strict, _ = self.solve(domain)
        _, penalized, _ = self.solve(domain, "penalized")
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertEqual((penalized.status, penalized.hard_penalty), ("OPTIMAL", 3))

    def test_convex_cut_is_global_lower_bound(self):
        domain = schedule()
        domain.lines.pop()
        for mode in ("strict", "penalized"):
            cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
            orders = list(permutations(cotwin.job_ids))
            for fixed in orders:
                selected = {
                    cotwin.arcs[20, a, b].index
                    for a, b in [
                        (None, fixed[0]),
                        (fixed[0], fixed[1]),
                        (fixed[-1], None),
                    ]
                }
                if mode == "strict":
                    selected.add(cotwin.operator_before[fixed[0], fixed[1]].index)
                cut = convex_cut(cotwin, selected, "cost", 1)
                self.assertIsNotNone(cut)
                intercept, coefficients = cut
                for other in orders:
                    trial = {
                        cotwin.arcs[20, a, b].index
                        for a, b in [
                            (None, other[0]),
                            (other[0], other[1]),
                            (other[-1], None),
                        ]
                    }
                    if mode == "strict":
                        trial.add(cotwin.operator_before[other[0], other[1]].index)
                    timing = earliest_schedule(
                        cotwin, {20: other}, [tuple(other)] if mode == "strict" else ()
                    )
                    lower = intercept + sum(
                        value for index, value in coefficients.items() if index in trial
                    )
                    actual = cotwin.facts.medium_weight * timing.medium + timing.ideal
                    if mode == "penalized":
                        actual += timing.overlap
                    self.assertLessEqual(lower, actual)

    def test_cut_remains_valid_when_line_assignment_changes(self):
        cotwin = CotwinBuilder(mode="strict").build_cotwin(
            schedule(shared_operator=True)
        )
        patterns = [
            ({20: (2, 7), 23: ()}, [(2, 7)]),
            ({20: (7, 2), 23: ()}, [(7, 2)]),
            ({20: (), 23: (2, 7)}, [(2, 7)]),
            ({20: (), 23: (7, 2)}, [(7, 2)]),
            ({20: (2,), 23: (7,)}, [(2, 7)]),
            ({20: (2,), 23: (7,)}, [(7, 2)]),
            ({20: (7,), 23: (2,)}, [(2, 7)]),
            ({20: (7,), 23: (2,)}, [(7, 2)]),
        ]

        def chosen(routes, order):
            result = set()
            for lid, route in routes.items():
                if route:
                    result.add(cotwin.arcs[lid, None, route[0]].index)
                    result.add(cotwin.arcs[lid, route[-1], None].index)
                    result.update(
                        cotwin.arcs[lid, a, b].index for a, b in zip(route, route[1:])
                    )
            result.update(cotwin.operator_before[a, b].index for a, b in order)
            return result

        cut = convex_cut(cotwin, chosen(*patterns[0]), "cost", 1)
        self.assertIsNotNone(cut)
        intercept, coefficients = cut
        for routes, order in patterns:
            timing = earliest_schedule(cotwin, routes, order)
            self.assertTrue(timing.feasible)
            selected = chosen(routes, order)
            lower = intercept + sum(
                value for index, value in coefficients.items() if index in selected
            )
            self.assertLessEqual(
                lower, cotwin.facts.medium_weight * timing.medium + timing.ideal
            )

    def test_matches_source_optimum_on_small_generated_instances(self):
        for mode in ("strict", "penalized"):
            with self.subTest(mode=mode):
                domain = DomainBuilder(
                    2, 3, start_date=datetime(2026, 9, 28).date()
                ).build_domain_from_scratch()
                _, result, _ = self.solve(domain, mode)
                with redirect_stdout(io.StringIO()):
                    source = SourceFoodPackagingSolver(workers=1, time_limit=5).solve(
                        SourceCotwinBuilder(mode=mode).build_cotwin(domain)
                    )
                self.assertEqual((result.status, source.status), ("OPTIMAL", "OPTIMAL"))
                self.assertEqual(
                    (result.hard_penalty, result.medium_penalty, result.soft_penalty),
                    (source.hard_penalty, source.medium_penalty, source.soft_penalty),
                )

    def test_idle_deadline_is_independent_of_master_progress(self):
        cotwin = CotwinBuilder().build_cotwin(PackagingSchedule())
        logger = ScoreNoImprovement(cotwin, 0.02, None)
        try:
            sleep(0.04)
            self.assertEqual(logger.remaining(), 0)
            self.assertEqual(logger.reason(), "no_improvement")
        finally:
            logger.close()

    def test_cli_and_input_validation(self):
        command = [
            sys.executable,
            "-m",
            "examples.or_tools.food_packaging_gbd.scripts.solve_task",
        ]
        help_run = subprocess.run(
            command + ["--help"], cwd=ROOT, capture_output=True, text=True, timeout=10
        )
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("--no-improvement-seconds", help_run.stdout)
        run = subprocess.run(
            command
            + [
                "--line-count",
                "1",
                "--job-count",
                "2",
                "--start-date",
                "2026-09-28",
                "--workers",
                "1",
                "--time-limit",
                "5",
                "--no-schedule",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("Mode: penalized", run.stdout)
        self.assertIn("GBD iterations:", run.stdout)
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="other")
        invalid = schedule()
        invalid.jobs[0].duration = timedelta(seconds=30)
        with self.assertRaisesRegex(ValueError, "minute-aligned"):
            CotwinBuilder().build_cotwin(invalid)
        invalid.jobs[0].duration = timedelta(days=10_000_000)
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder().build_cotwin(invalid)


if __name__ == "__main__":
    unittest.main()
