import io
import itertools
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from datetime import date

from ortools.sat.python import cp_model

from examples.or_tools.maintenance_scheduling.domain import (
    Crew,
    Job,
    MaintenanceSchedule,
    WorkCalendar,
)
from examples.or_tools.maintenance_scheduling.persistence import (
    CotwinBuilder,
    DomainBuilder,
)
from examples.or_tools.maintenance_scheduling.solver import (
    MaintenanceSchedulingSolution,
    MaintenanceSchedulingSolver,
)


MONDAY = date(2026, 9, 28)


def tiny_schedule() -> MaintenanceSchedule:
    return MaintenanceSchedule(
        WorkCalendar(0, MONDAY, date(2026, 10, 5)),
        [Crew(42, "North"), Crew(99, "South")],
        [
            Job(
                10,
                "First",
                2,
                date(2026, 9, 30),
                date(2026, 10, 2),
                date(2026, 10, 2),
                ("Area",),
            ),
            Job(
                7,
                "Second",
                1,
                None,
                None,
                date(2026, 9, 30),
                ("Area",),
            ),
        ],
    )


class MaintenanceSchedulingTests(unittest.TestCase):
    def test_generated_data_and_source_calendar_boundaries(self) -> None:
        for size, crew_count, job_count, workdays, weeks in (
            ("small", 3, 14, 40, 8),
            ("large", 5, 48, 80, 16),
        ):
            domain = DomainBuilder(size, MONDAY).build_domain_from_scratch()
            self.assertEqual(
                (len(domain.crews), len(domain.jobs)), (crew_count, job_count)
            )
            self.assertEqual(len(domain.work_calendar.work_day_list), workdays)
            self.assertEqual(domain.work_calendar.work_day_list[0], date(2026, 9, 29))
            self.assertEqual(
                domain.work_calendar.work_day_list[-1],
                domain.work_calendar.to_date,
            )
            self.assertEqual((domain.work_calendar.to_date - MONDAY).days, weeks * 7)
        source = DomainBuilder("small", MONDAY).build_domain_from_scratch()
        self.assertEqual(
            (
                source.jobs[0].name,
                source.jobs[0].duration_in_days,
                source.jobs[0].min_start_date,
                source.jobs[0].ideal_end_date,
            ),
            ("Downtown Street", 3, date(2026, 10, 19), date(2026, 10, 30)),
        )

    def test_source_penalty_components(self) -> None:
        domain = tiny_schedule()
        domain.jobs[0].crew_id = 42
        domain.jobs[0].start_date_id = 0  # Tuesday to Thursday.
        domain.jobs[1].crew_id = 42
        domain.jobs[1].start_date_id = 1  # Wednesday to Thursday.
        metrics = domain.calculate_metrics()
        self.assertEqual(metrics["early_start_penalty"], 1)
        self.assertEqual(metrics["late_end_penalty"], 0)
        self.assertEqual(metrics["crew_overlap_penalty"], 2)
        self.assertEqual(metrics["before_ideal_penalty"], 1)
        self.assertEqual(metrics["after_ideal_penalty"], 1_000_000)
        self.assertEqual(metrics["tag_penalty"], 2_000)
        self.assertEqual(
            (metrics["hard_penalty"], metrics["soft_penalty"]), (3, 1_002_001)
        )

        # Separated jobs on the same crew still pay the source's abs(raw) tag cost.
        domain.jobs[0].start_date_id = 0  # End Wednesday after one workday.
        domain.jobs[0].duration_in_days = 1
        domain.jobs[1].start_date_id = 3  # Friday to following Monday.
        separated = domain.calculate_metrics()
        self.assertEqual(separated["crew_overlap_penalty"], 0)
        self.assertEqual(separated["tag_penalty"], 4_000)
        domain.jobs[1].crew_id = 99
        self.assertEqual(domain.calculate_metrics()["tag_penalty"], 0)

    def test_model_components_match_business_scores_for_fixed_assignments(self) -> None:
        cases = (
            ((42, 0), (42, 1)),  # Overlapping jobs on one crew.
            ((42, 0), (42, 4)),  # Separated jobs still incur the tag penalty.
            ((42, 1), (99, 0)),  # Different crews; both ideal dates match.
            ((42, 2), (42, 0)),  # Late end and separated jobs on one crew.
        )
        for assignments in cases:
            with self.subTest(assignments=assignments):
                original = tiny_schedule()
                expected = deepcopy(original)
                cotwin = CotwinBuilder(mode="penalized").build_cotwin(original)
                for job, (crew_id, start_index) in zip(expected.jobs, assignments):
                    job.crew_id = crew_id
                    job.start_date_id = start_index
                    cotwin.model.add(
                        cotwin.crew_variables[job.job_id]
                        == cotwin.crew_ids.index(crew_id)
                    )
                    cotwin.model.add(cotwin.start_variables[job.job_id] == start_index)

                metrics = expected.calculate_metrics()
                solver = cp_model.CpSolver()
                self.assertEqual(solver.solve(cotwin.model), cp_model.OPTIMAL)
                for name, variable in cotwin.penalty_components.items():
                    self.assertEqual(solver.value(variable), metrics[name], name)
                self.assertEqual(
                    solver.value(cotwin.hard_penalty), metrics["hard_penalty"]
                )
                self.assertEqual(
                    solver.value(cotwin.soft_penalty), metrics["soft_penalty"]
                )

    def test_beyond_calendar_end_and_ideal_equality(self) -> None:
        domain = MaintenanceSchedule(
            WorkCalendar(0, MONDAY, date(2026, 10, 5)),
            [Crew(3, "Only")],
            [Job(5, "End", 2, None, date(2026, 10, 6), date(2026, 10, 7), (), 3, 4)],
        )
        self.assertEqual(domain.work_calendar.end_date(4, 2), date(2026, 10, 7))
        metrics = domain.calculate_metrics()
        self.assertEqual(metrics["late_end_penalty"], 1)
        self.assertEqual(metrics["before_ideal_penalty"], 0)
        self.assertEqual(metrics["after_ideal_penalty"], 0)

    def test_solver_matches_exhaustive_business_scoring(self) -> None:
        original = tiny_schedule()
        crew_ids = [crew.crew_id for crew in original.crews]
        workday_ids = range(len(original.work_calendar.work_day_list))
        scores = []
        for left, right in itertools.product(
            itertools.product(crew_ids, workday_ids), repeat=2
        ):
            candidate = deepcopy(original)
            for job, assignment in zip(candidate.jobs, (left, right)):
                job.crew_id, job.start_date_id = assignment
            metrics = candidate.calculate_metrics()
            scores.append((metrics["hard_penalty"], metrics["soft_penalty"]))
        best_penalized = min(scores)
        best_strict = min(soft for hard, soft in scores if hard == 0)
        for mode, expected in (
            ("penalized", best_penalized),
            ("strict", (0, best_strict)),
        ):
            with self.subTest(mode=mode), redirect_stdout(io.StringIO()):
                cotwin = CotwinBuilder(mode=mode).build_cotwin(original)
                solution = MaintenanceSchedulingSolver(
                    workers=1, no_improvement_seconds=5, time_limit=5
                ).solve(cotwin)
                self.assertEqual(solution.status, "OPTIMAL")
                self.assertEqual(
                    (solution.hard_penalty, solution.soft_penalty), expected
                )
                rebuilt = DomainBuilder(start_date=MONDAY).build_from_solution(
                    solution, initial_domain=original
                )
                self.assertEqual(
                    (
                        rebuilt.calculate_metrics()["hard_penalty"],
                        rebuilt.calculate_metrics()["soft_penalty"],
                    ),
                    expected,
                )
                self.assertTrue(all(job.crew_id is None for job in original.jobs))

    def test_reconstruction_validates_ids_and_scores(self) -> None:
        original = tiny_schedule()
        assignments = {10: (42, 0), 7: (99, 1)}
        expected = deepcopy(original)
        for job in expected.jobs:
            job.crew_id, job.start_date_id = assignments[job.job_id]
        metrics = expected.calculate_metrics()
        solution = MaintenanceSchedulingSolution(
            "FEASIBLE",
            assignments,
            metrics["hard_penalty"],
            metrics["soft_penalty"],
            0.1,
            "time_limit",
            "penalized",
        )
        builder = DomainBuilder(start_date=MONDAY)
        rebuilt = builder.build_from_solution(solution, initial_domain=original)
        self.assertEqual(rebuilt.calculate_metrics(), metrics)
        self.assertIsNone(original.jobs[0].crew_id)
        with self.assertRaisesRegex(ValueError, "scores do not match"):
            builder.build_from_solution(
                replace(solution, soft_penalty=solution.soft_penalty + 1),
                initial_domain=original,
            )
        with self.assertRaisesRegex(ValueError, "exactly the domain"):
            builder.build_from_solution(
                replace(solution, assignments={10: (42, 0)}),
                initial_domain=original,
            )

    def test_strict_infeasibility_has_no_assignment(self) -> None:
        domain = MaintenanceSchedule(
            WorkCalendar(0, MONDAY, date(2026, 9, 29)),
            [Crew(5, "Only")],
            [
                Job(2, "A", 1, None, None, None, ()),
                Job(8, "B", 1, None, None, None, ()),
            ],
        )
        with redirect_stdout(io.StringIO()):
            solution = MaintenanceSchedulingSolver(
                workers=1, no_improvement_seconds=5, time_limit=5
            ).solve(CotwinBuilder(mode="strict").build_cotwin(domain))
        self.assertEqual(solution.status, "INFEASIBLE")
        self.assertFalse(solution.has_solution)
        self.assertIsNone(solution.assignments)

    def test_impossible_date_window_is_penalized_only(self) -> None:
        domain = MaintenanceSchedule(
            WorkCalendar(0, MONDAY, date(2026, 9, 29)),
            [Crew(5, "Only")],
            [
                Job(
                    2,
                    "Late",
                    1,
                    date(2026, 9, 30),
                    date(2026, 9, 29),
                    None,
                    (),
                )
            ],
        )
        with redirect_stdout(io.StringIO()):
            strict = MaintenanceSchedulingSolver(workers=1, time_limit=5).solve(
                CotwinBuilder(mode="strict").build_cotwin(domain)
            )
            penalized = MaintenanceSchedulingSolver(workers=1, time_limit=5).solve(
                CotwinBuilder(mode="penalized").build_cotwin(domain)
            )
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)
        self.assertEqual(penalized.status, "OPTIMAL")
        self.assertEqual(penalized.hard_penalty, 2)
        self.assertEqual(penalized.soft_penalty, 0)


if __name__ == "__main__":
    unittest.main()
