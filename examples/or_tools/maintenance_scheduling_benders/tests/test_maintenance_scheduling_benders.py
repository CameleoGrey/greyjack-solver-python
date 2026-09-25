import io
import itertools
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from ortools.sat.python import cp_model

from examples.or_tools.maintenance_scheduling_benders.domain import (
    Crew,
    Job,
    MaintenanceSchedule,
    WorkCalendar,
)
from examples.or_tools.maintenance_scheduling_benders.persistence import (
    CotwinBuilder,
    DomainBuilder,
)
from examples.or_tools.maintenance_scheduling_benders.solver import (
    MaintenanceSchedulingSolver,
)
from examples.or_tools.maintenance_scheduling_benders.solver.ScoreNoImprovement import (
    ScoreNoImprovement,
)
from examples.or_tools.maintenance_scheduling_benders.solver.MaintenanceSchedulingSolver import (
    _CrewResult,
)


MONDAY = date(2026, 9, 28)


def small_oracle_schedule() -> MaintenanceSchedule:
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
            Job(7, "Second", 1, None, None, date(2026, 9, 30), ("Area",)),
            Job(25, "Third", 1, None, None, date(2026, 10, 1), ("Area",)),
        ],
    )


def oracle_scores(
    domain: MaintenanceSchedule,
) -> tuple[tuple[int, int], tuple[int, int]]:
    choices = list(
        itertools.product(
            (crew.crew_id for crew in domain.crews),
            range(len(domain.work_calendar.work_day_list)),
        )
    )
    scores = []
    for selected in itertools.product(choices, repeat=len(domain.jobs)):
        candidate = deepcopy(domain)
        for job, (crew_id, start_id) in zip(candidate.jobs, selected):
            job.crew_id, job.start_date_id = crew_id, start_id
        metrics = candidate.calculate_metrics()
        scores.append((metrics["hard_penalty"], metrics["soft_penalty"]))
    penalized = min(scores)
    strict = (0, min(soft for hard, soft in scores if hard == 0))
    return strict, penalized


class BendersMaintenanceTests(unittest.TestCase):
    def test_capacity_bounds_hold_for_exhaustive_business_schedules(self) -> None:
        domain = small_oracle_schedule()
        for mode in ("strict", "penalized"):
            cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
            windows = MaintenanceSchedulingSolver._capacity_windows(cotwin)
            choices = list(
                itertools.product(cotwin.crew_ids, range(len(cotwin.start_days)))
            )
            for selected in itertools.product(choices, repeat=len(domain.jobs)):
                schedule = deepcopy(domain)
                for job, (cid, day) in zip(schedule.jobs, selected):
                    job.crew_id, job.start_date_id = cid, day
                if mode == "strict" and schedule.calculate_metrics()["hard_penalty"]:
                    continue
                for cid in cotwin.crew_ids:
                    crew_schedule = deepcopy(schedule)
                    crew_schedule.crews = [
                        crew for crew in crew_schedule.crews if crew.crew_id == cid
                    ]
                    crew_schedule.jobs = [
                        job for job in crew_schedule.jobs if job.crew_id == cid
                    ]
                    metrics = crew_schedule.calculate_metrics()
                    exact = metrics["soft_penalty"]
                    if mode == "penalized":
                        exact += cotwin.hard_weight * metrics["hard_penalty"]
                    baseline = sum(
                        cotwin.individual_costs[job.job_id]
                        for job in crew_schedule.jobs
                    )
                    for left, right, minimum in windows:
                        load = sum(minimum[job.job_id] for job in crew_schedule.jobs)
                        if mode == "strict":
                            self.assertLessEqual(load, right - left)
                        else:
                            self.assertGreaterEqual(
                                exact,
                                baseline
                                + 2 * cotwin.hard_weight * (load - (right - left)),
                            )

    def test_unresolved_crew_search_cannot_prove_optimality(self) -> None:
        domain = small_oracle_schedule()
        cotwin = CotwinBuilder(mode="penalized").build_cotwin(domain)

        def weak_seed(self, instance, logger, deadline):
            candidate = {
                job.job_id: (instance.crew_ids[0], 0) for job in instance.domain.jobs
            }
            logger.record(self._replay(instance, candidate), candidate)

        with (
            patch.object(MaintenanceSchedulingSolver, "_seed", weak_seed),
            patch.object(
                MaintenanceSchedulingSolver,
                "_solve_crew",
                return_value=_CrewResult(cp_model.UNKNOWN, None, None, None, None),
            ),
            redirect_stdout(io.StringIO()),
        ):
            solution = MaintenanceSchedulingSolver(
                workers=1, no_improvement_seconds=1, time_limit=1
            ).solve(cotwin)
        self.assertEqual(solution.status, "FEASIBLE")
        self.assertGreater(solution.iterations, 0)
        self.assertEqual(
            solution.cuts, solution.capacity_cuts + solution.subproblem_cuts
        )

    def test_source_calendar_boundaries_and_overflow(self) -> None:
        calendar = WorkCalendar(0, MONDAY, date(2026, 10, 5))
        self.assertEqual(calendar.work_day_list[0], date(2026, 9, 29))
        self.assertEqual(calendar.work_day_list[-1], date(2026, 10, 5))
        self.assertEqual(calendar.end_date(4, 2), date(2026, 10, 7))

    def test_both_modes_match_exhaustive_business_oracle(self) -> None:
        domain = small_oracle_schedule()
        strict_score, penalized_score = oracle_scores(domain)
        for mode, expected in (
            ("strict", strict_score),
            ("penalized", penalized_score),
        ):
            with self.subTest(mode=mode), redirect_stdout(io.StringIO()):
                cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
                solution = MaintenanceSchedulingSolver(
                    workers=1, no_improvement_seconds=10, time_limit=10
                ).solve(cotwin)
                self.assertEqual(solution.status, "OPTIMAL")
                self.assertEqual(
                    (solution.hard_penalty, solution.soft_penalty), expected
                )
                rebuilt = DomainBuilder(start_date=MONDAY).build_from_solution(
                    solution, initial_domain=domain
                )
                self.assertEqual(
                    (
                        rebuilt.calculate_metrics()["hard_penalty"],
                        rebuilt.calculate_metrics()["soft_penalty"],
                    ),
                    expected,
                )
                self.assertTrue(all(job.crew_id is None for job in domain.jobs))

    def test_same_crew_tag_cost_for_separated_jobs(self) -> None:
        domain = MaintenanceSchedule(
            WorkCalendar(0, MONDAY, date(2026, 10, 5)),
            [Crew(3, "Only")],
            [
                Job(
                    2,
                    "Early",
                    1,
                    date(2026, 9, 29),
                    date(2026, 9, 30),
                    date(2026, 9, 30),
                    ("Shared",),
                ),
                Job(
                    8,
                    "Late",
                    1,
                    date(2026, 10, 2),
                    date(2026, 10, 5),
                    date(2026, 10, 5),
                    ("Shared",),
                ),
            ],
        )
        with redirect_stdout(io.StringIO()):
            solution = MaintenanceSchedulingSolver(workers=1, time_limit=5).solve(
                CotwinBuilder(mode="strict").build_cotwin(domain)
            )
        self.assertEqual(solution.status, "OPTIMAL")
        rebuilt = DomainBuilder(start_date=MONDAY).build_from_solution(
            solution, initial_domain=domain
        )
        self.assertEqual(rebuilt.calculate_metrics()["tag_penalty"], 4_000)
        self.assertEqual((solution.hard_penalty, solution.soft_penalty), (0, 4_000))
        self.assertGreater(solution.cuts, 0)

    def test_fixed_penalized_subproblem_matches_business_replay(self) -> None:
        domain = small_oracle_schedule()
        cotwin = CotwinBuilder(mode="penalized").build_cotwin(domain)
        subproblem = CotwinBuilder(mode="penalized").build_crew_subproblem(
            cotwin, frozenset(job.job_id for job in domain.jobs)
        )
        starts = {10: 0, 7: 1, 25: 4}
        for jid, day in starts.items():
            subproblem.model.add(subproblem.start_variables[jid] == day)
        solver = cp_model.CpSolver()
        self.assertEqual(solver.solve(subproblem.model), cp_model.OPTIMAL)
        replay = deepcopy(domain)
        for job in replay.jobs:
            job.crew_id, job.start_date_id = 42, starts[job.job_id]
        metrics = replay.calculate_metrics()
        self.assertEqual(solver.value(subproblem.hard_penalty), metrics["hard_penalty"])
        self.assertEqual(solver.value(subproblem.soft_penalty), metrics["soft_penalty"])

    def test_native_large_penalized_subproblem_has_safe_objective_bounds(self) -> None:
        domain = DomainBuilder("large", MONDAY).build_domain_from_scratch()
        builder = CotwinBuilder(mode="penalized")
        cotwin = builder.build_cotwin(domain)
        subproblem = builder.build_crew_subproblem(
            cotwin, frozenset((domain.jobs[0].job_id, domain.jobs[1].job_id))
        )
        self.assertEqual(subproblem.model.validate(), "")

    def test_strict_infeasibility_is_proved(self) -> None:
        domain = MaintenanceSchedule(
            WorkCalendar(0, MONDAY, date(2026, 9, 29)),
            [Crew(5, "Only")],
            [
                Job(2, "A", 1, None, None, None, ()),
                Job(8, "B", 1, None, None, None, ()),
            ],
        )
        with redirect_stdout(io.StringIO()):
            solution = MaintenanceSchedulingSolver(workers=1, time_limit=5).solve(
                CotwinBuilder(mode="strict").build_cotwin(domain)
            )
        self.assertEqual(solution.status, "INFEASIBLE")
        self.assertFalse(solution.has_solution)
        self.assertGreater(solution.cuts, 0)

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
        self.assertEqual(penalized.status, "OPTIMAL")
        self.assertEqual((penalized.hard_penalty, penalized.soft_penalty), (2, 0))

    def test_logger_resets_only_for_strict_improvements(self) -> None:
        clock = [0.0]
        output = io.StringIO()
        with (
            patch(
                "examples.or_tools.maintenance_scheduling_benders.solver.ScoreNoImprovement.monotonic",
                side_effect=lambda: clock[0],
            ),
            redirect_stdout(output),
        ):
            logger = ScoreNoImprovement(0.0, 5.0)
            clock[0] = 1.0
            self.assertTrue(logger.record((1, 10), {2: (3, 4)}))
            self.assertEqual(logger.deadline, 6.0)
            clock[0] = 3.0
            self.assertFalse(logger.record((1, 10), {2: (3, 2)}))
            self.assertEqual(logger.deadline, 6.0)
            self.assertFalse(logger.record((2, 0), {2: (3, 2)}))
            clock[0] = 4.0
            self.assertTrue(logger.record((0, 100), {2: (3, 1)}))
            self.assertEqual(logger.deadline, 9.0)
        self.assertEqual(output.getvalue().count("New best solution"), 2)
        self.assertEqual(logger.best_assignments, {2: (3, 1)})


if __name__ == "__main__":
    unittest.main()
