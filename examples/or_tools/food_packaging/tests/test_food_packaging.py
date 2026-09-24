import importlib
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from examples.or_tools.food_packaging.domain import (
    Job,
    Line,
    PackagingSchedule,
    Product,
)
from examples.or_tools.food_packaging.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.food_packaging.persistence.DemoDataGenerator import (
    DemoDataGenerator,
)
from examples.or_tools.food_packaging.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.food_packaging.solver.FoodPackagingSolver import (
    FoodPackagingSolver,
)


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "examples/or_tools/food_packaging/scripts/solve_task.py"
BASE = datetime(2026, 9, 28)


def make_schedule(line_count=1, products=1, operator_names=None):
    product_list = [Product(100 + 7 * i, f"Product {i}") for i in range(products)]
    for product in product_list:
        for previous in product_list:
            product.cleaning_durations[previous] = timedelta(0)
    operators = operator_names or [f"Operator {i}" for i in range(line_count)]
    lines = [
        Line(20 + 3 * i, f"Line {i}", operators[i], BASE) for i in range(line_count)
    ]
    return PackagingSchedule(product_list, lines, [])


def add_job(
    schedule,
    job_id,
    product_index=0,
    minutes=60,
    min_minutes=0,
    ideal_minutes=1440,
    max_minutes=2880,
    priority=1,
):
    job = Job(
        job_id,
        f"Job {job_id}",
        schedule.products[product_index],
        timedelta(minutes=minutes),
        BASE + timedelta(minutes=min_minutes),
        BASE + timedelta(minutes=ideal_minutes),
        BASE + timedelta(minutes=max_minutes),
        priority,
    )
    schedule.jobs.append(job)
    return job


class FoodPackagingTests(unittest.TestCase):
    def solve(self, schedule, mode="strict", hints=True):
        cotwin = CotwinBuilder(mode=mode, use_greedy_hints=hints).build_cotwin(schedule)
        with redirect_stdout(io.StringIO()):
            result = FoodPackagingSolver(
                workers=1, no_improvement_seconds=2, time_limit=5
            ).solve(cotwin)
        return result

    def replay(self, schedule, result):
        return DomainBuilder().build_from_solution(result, initial_domain=schedule)

    def test_directional_cleaning_before_incoming_job(self):
        schedule = make_schedule(products=2)
        first, second = schedule.products
        first.cleaning_durations[second] = timedelta(minutes=2)
        second.cleaning_durations[first] = timedelta(minutes=7)
        add_job(schedule, 8, 0, minutes=10, priority=3)
        add_job(schedule, -3, 1, minutes=10)
        for mode in ("strict", "penalized"):
            with self.subTest(mode=mode):
                result = self.solve(schedule, mode)
                self.assertEqual(result.status, "OPTIMAL")
                self.assertEqual(result.line_routes[20], (-3, 8))
                self.assertEqual(
                    (result.hard_penalty, result.medium_penalty, result.soft_penalty),
                    (0, 22**2, 6),
                )
                solved = self.replay(schedule, result)
                self.assertEqual(
                    solved.jobs[0].start_time, BASE + timedelta(minutes=12)
                )
                self.assertEqual(solved.jobs[0].end_time, BASE + timedelta(minutes=22))
                self.assertTrue(all(job.start_time is None for job in schedule.jobs))

    def test_medium_score_precedes_large_soft_cleaning_cost(self):
        schedule = make_schedule(products=2)
        first, second = schedule.products
        first.cleaning_durations[second] = timedelta(minutes=1)
        second.cleaning_durations[first] = timedelta(minutes=2)
        add_job(schedule, 1, 0, minutes=10, priority=1_000_000)
        add_job(schedule, 2, 1, minutes=10, priority=1)
        for mode in ("strict", "penalized"):
            result = self.solve(schedule, mode)
            self.assertEqual(result.line_routes[20], (2, 1))
            self.assertEqual(result.medium_penalty, 21**2)
            self.assertEqual(result.soft_penalty, 1_000_000)

    def test_penalized_hard_score_precedes_smaller_makespan(self):
        schedule = make_schedule(2)
        schedule.lines[1].start_date_time = BASE + timedelta(minutes=100)
        add_job(schedule, 1, minutes=10, max_minutes=30)
        add_job(schedule, 2, minutes=10, max_minutes=30)
        result = self.solve(schedule, "penalized")
        self.assertEqual(result.hard_penalty, 0)
        self.assertEqual(result.medium_penalty, 20**2)
        self.assertEqual(result.line_routes[20], (1, 2))

    def test_strict_uses_full_deadline_and_returns_no_fallback(self):
        schedule = make_schedule()
        add_job(
            schedule, 5, minutes=17 * 60, ideal_minutes=16 * 60, max_minutes=16 * 60
        )
        strict = self.solve(schedule, "strict")
        penalized = self.solve(schedule, "penalized")
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)
        self.assertEqual((penalized.hard_penalty, penalized.soft_penalty), (60, 60))
        self.assertEqual(
            self.replay(schedule, penalized).calculate_metrics()["late_minutes"], 60
        )

    def test_earliest_start_is_hard_only_in_strict_mode(self):
        schedule = make_schedule()
        add_job(schedule, 91, min_minutes=600)
        strict = self.solve(schedule, "strict")
        penalized = self.solve(schedule, "penalized")
        self.assertEqual(strict.start_times[91], BASE + timedelta(minutes=600))
        self.assertEqual(penalized.start_times[91], BASE)
        self.assertEqual(strict.medium_penalty, 660**2)
        self.assertEqual(penalized.medium_penalty, 60**2)

    def test_shared_operator_is_reserved_for_production_only_in_strict_mode(self):
        schedule = make_schedule(2, operator_names=["Same", "Same"])
        add_job(schedule, 1)
        add_job(schedule, 2)
        strict = self.solve(schedule, "strict")
        penalized = self.solve(schedule, "penalized")
        self.assertTrue(
            self.replay(schedule, strict).calculate_metrics()["strict_feasible"]
        )
        self.assertEqual(strict.soft_penalty, 0)
        self.assertEqual(penalized.medium_penalty, 2 * 60**2)
        self.assertEqual(penalized.soft_penalty, 60)
        self.assertEqual(
            self.replay(schedule, penalized).calculate_metrics()[
                "operator_overlap_minutes"
            ],
            60,
        )

    def test_operator_deadlines_can_make_strict_mode_infeasible(self):
        schedule = make_schedule(2, operator_names=["Same", "Same"])
        add_job(schedule, 1, max_minutes=60)
        add_job(schedule, 2, max_minutes=60)
        strict = self.solve(schedule, "strict")
        penalized = self.solve(schedule, "penalized")
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)
        self.assertEqual(penalized.hard_penalty, 0)
        self.assertEqual(penalized.soft_penalty, 60)

    def test_score_replay_rejects_broken_solution_and_keeps_input(self):
        schedule = make_schedule(2, operator_names=["A", "B"])
        add_job(schedule, 701)
        add_job(schedule, -20)
        before = deepcopy(schedule)
        result = self.solve(schedule)
        solved = self.replay(schedule, result)
        self.assertEqual(set(result.start_times), {701, -20})
        self.assertEqual(
            set(job.id for line in solved.lines for job in line.jobs), {701, -20}
        )
        self.assertEqual(
            [line.jobs for line in schedule.lines], [line.jobs for line in before.lines]
        )
        self.assertTrue(all(job.line is None for job in schedule.jobs))
        for broken in (
            replace(result, line_routes={20: (701,)}),
            replace(result, start_times={}),
            replace(result, medium_penalty=result.medium_penalty + 1),
            replace(result, status="UNKNOWN", line_routes=None),
        ):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                self.replay(schedule, broken)

    def test_generator_matches_original_fixed_date_facts(self):
        source = importlib.import_module(
            "examples.object_oriented.food_packaging.persistence.DemoDataGenerator"
        )

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 9, 24)

        with patch.object(source, "datetime", FrozenDateTime):
            original = source.DemoDataGenerator(5, 100).generate_demo_data()
        new = DemoDataGenerator(
            5, 100, start_date=date(2026, 9, 28)
        ).generate_demo_data()
        self.assertEqual(
            (len(new.products), len(new.lines), len(new.jobs)), (60, 5, 100)
        )
        for old, current in zip(original.products, new.products):
            self.assertEqual((old.id, old.name), (current.id, current.name))
        for old, current in zip(original.products, new.products):
            self.assertEqual(
                [old.cleaning_durations[x] for x in original.products],
                [current.cleaning_durations[x] for x in new.products],
            )
        for old, current in zip(original.jobs, new.jobs):
            self.assertEqual(
                (
                    old.id,
                    old.name,
                    old.product.id,
                    old.duration,
                    old.min_start_time,
                    old.ideal_end_time,
                    old.max_end_time,
                    old.priority,
                ),
                (
                    current.id,
                    current.name,
                    current.product.id,
                    current.duration,
                    current.min_start_time,
                    current.ideal_end_time,
                    current.max_end_time,
                    current.priority,
                ),
            )

    def test_generator_round_trip_without_initial_domain(self):
        builder = DomainBuilder(2, 4, seed=37, start_date=date(2026, 9, 28))
        initial = builder.build_domain_from_scratch()
        result = self.solve(initial)
        restored = builder.build_from_solution(result)
        self.assertEqual(
            restored.calculate_metrics()["medium_penalty"], result.medium_penalty
        )
        self.assertTrue(all(job.start_time is None for job in initial.jobs))

    def test_empty_and_invalid_domains(self):
        empty = PackagingSchedule()
        result = self.solve(empty)
        self.assertEqual(result.status, "OPTIMAL")
        self.assertEqual(result.line_routes, {})
        self.assertEqual(result.start_times, {})
        self.assertEqual(empty.calculate_metrics()["medium_penalty"], 0)
        generated_empty = DemoDataGenerator(
            2, 0, start_date=date(2026, 9, 28)
        ).generate_demo_data()
        self.assertEqual(self.solve(generated_empty).status, "OPTIMAL")
        invalid = make_schedule()
        invalid.jobs.append(
            Job(
                1,
                "Bad",
                invalid.products[0],
                timedelta(minutes=1),
                BASE,
                BASE,
                BASE,
                pinned=True,
            )
        )
        with self.assertRaisesRegex(ValueError, "Pinned"):
            CotwinBuilder().build_cotwin(invalid)
        invalid.jobs[0].pinned = False
        invalid.jobs[0].duration = timedelta(seconds=30)
        with self.assertRaisesRegex(ValueError, "minute-aligned"):
            CotwinBuilder().build_cotwin(invalid)
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="wrong")

    def test_large_time_values_reject_unsafe_bounds(self):
        schedule = make_schedule()
        add_job(schedule, 1)
        schedule.jobs[0].duration = timedelta(days=10_000_000)
        with self.assertRaisesRegex(ValueError, "integer bounds"):
            CotwinBuilder().build_cotwin(schedule)

    def test_cli_direct_and_module_help(self):
        direct = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--line-count",
                "2",
                "--job-count",
                "4",
                "--start-date",
                "2026-09-28",
                "--workers",
                "1",
                "--time-limit",
                "5",
                "--no-schedule",
            ],
            cwd="/tmp",
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertIn("Mode: strict", direct.stdout)
        self.assertIn("strict_feasible: True", direct.stdout)
        module = subprocess.run(
            [
                sys.executable,
                "-m",
                "examples.or_tools.food_packaging.scripts.solve_task",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(module.returncode, 0, module.stderr)
        self.assertIn("--mode", module.stdout)


if __name__ == "__main__":
    unittest.main()
