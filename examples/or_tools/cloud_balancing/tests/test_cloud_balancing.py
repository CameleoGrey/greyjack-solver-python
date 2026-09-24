import io
import itertools
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ortools.sat.python import cp_model

from examples.or_tools.cloud_balancing.domain.Computer import Computer
from examples.or_tools.cloud_balancing.domain.Process import Process
from examples.or_tools.cloud_balancing.domain.ScheduleCB import ScheduleCB
from examples.or_tools.cloud_balancing.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.cloud_balancing.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.cloud_balancing.solver.CloudBalancingSolver import (
    CloudBalancingSolver,
)
from examples.or_tools.cloud_balancing.solver.ScoreNoImprovement import (
    ScoreNoImprovement,
)


SOLVER_MODULE = "examples.or_tools.cloud_balancing.solver.CloudBalancingSolver"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (
    PROJECT_ROOT / "examples/or_tools/cloud_balancing/scripts/solve_cloud_balancing.py"
)


def make_domain(computers, processes):
    return ScheduleCB(
        [Computer(10 + 7 * i, *values) for i, values in enumerate(computers)],
        [Process(100 + 11 * i, *values) for i, values in enumerate(processes)],
    )


def independent_score(domain, assignment):
    """Oracle that does not use model expressions or domain metric helpers."""
    hard = 0
    soft = 0
    for computer in domain.computers:
        processes = [
            p
            for p in domain.processes
            if assignment[p.process_id] == computer.computer_id
        ]
        if not processes:
            continue
        soft += computer.cost
        hard += max(0, sum(p.cpu_power_req for p in processes) - computer.cpu_power)
        hard += max(0, sum(p.memory_size_req for p in processes) - computer.memory_size)
        hard += max(
            0,
            sum(p.network_bandwidth_req for p in processes)
            - computer.network_bandwidth,
        )
    return hard, soft


class CloudBalancingTests(unittest.TestCase):
    def solve(self, domain, hints=True):
        cotwin = CotwinBuilder(use_greed_init=hints).build_cotwin(domain)
        return CloudBalancingSolver(
            workers=1, no_improvement_seconds=2, time_limit=5
        ).solve(cotwin)

    def test_scores_match_exhaustive_enumeration(self):
        cases = [
            ([(3, 3, 3, 7)], [(1, 1, 1), (2, 2, 2)]),
            ([(1, 3, 3, 7)], [(2, 1, 1)]),
            ([(3, 1, 3, 7)], [(1, 2, 1)]),
            ([(3, 3, 1, 7)], [(1, 1, 2)]),
            ([(0, 0, 0, 7)], [(1, 2, 3)]),
            ([(2, 2, 2, 1), (3, 3, 3, 100)], [(1, 1, 1)] * 3),
            ([(1, 1, 1, 1), (1, 1, 1, 9)], [(2, 2, 2)]),
            (
                [(2, 3, 1, 3), (3, 1, 2, 5), (1, 2, 3, 2)],
                [(1, 2, 1), (2, 0, 2), (1, 1, 0)],
            ),
            ([(0, 0, 0, 0), (0, 0, 0, 7)], [(0, 0, 0)] * 2),
            ([(3, 3, 3, 7)], []),
            ([], []),
        ]
        for computers, processes in cases:
            domain = make_domain(computers, processes)
            candidates = itertools.product(
                [c.computer_id for c in domain.computers], repeat=len(domain.processes)
            )
            optimum = min(
                independent_score(
                    domain, dict(zip((p.process_id for p in domain.processes), ids))
                )
                for ids in candidates
            )
            for hints in (False, True):
                with self.subTest(
                    computers=computers, processes=processes, hints=hints
                ):
                    result = self.solve(domain, hints)
                    self.assertEqual(result.status, "OPTIMAL")
                    self.assertEqual((result.hard_penalty, result.soft_cost), optimum)
                    self.assertEqual(
                        independent_score(domain, result.assignments), optimum
                    )

    def test_hard_penalty_has_priority_over_cost(self):
        domain = make_domain([(2, 2, 2, 1), (3, 3, 3, 100)], [(1, 1, 1)] * 3)
        result = self.solve(domain)
        self.assertEqual((result.hard_penalty, result.soft_cost), (0, 100))

    def test_unavoidable_overload_is_a_solution(self):
        domain = make_domain([(0, 0, 0, 7)], [(1, 2, 3)])
        result = self.solve(domain)
        solved = DomainBuilder(Path("unused.json")).build_from_solution(result, domain)
        metrics = solved.calculate_metrics()
        self.assertTrue(result.has_solution)
        self.assertFalse(metrics["resource_feasible"])
        self.assertEqual(metrics["hard_penalty"], 6)
        self.assertEqual(metrics["total_violations"], 3)

    def test_cost_is_charged_once_for_zero_demand_processes(self):
        domain = make_domain([(0, 0, 0, 5)], [(0, 0, 0)] * 3)
        self.assertEqual(self.solve(domain).soft_cost, 5)

    def test_usage_flags_are_exact_even_when_all_costs_are_zero(self):
        domain = make_domain([(0, 0, 0, 0), (0, 0, 0, 0)], [(0, 0, 0)])
        cotwin = CotwinBuilder().build_cotwin(domain)
        solver = cp_model.CpSolver()
        self.assertEqual(solver.solve(cotwin.model), cp_model.OPTIMAL)
        for cid, used in cotwin.computer_used.items():
            self.assertEqual(
                solver.value(used), solver.value(cotwin.assignment_variables[100][cid])
            )

    def test_scores_above_float_integer_precision_remain_exact(self):
        domain = make_domain([(1, 1, 1, 2**53 + 3), (1, 1, 1, 2**53 + 4)], [(1, 1, 1)])
        self.assertEqual(self.solve(domain).soft_cost, 2**53 + 3)

    def test_json_and_solution_round_trip_preserve_ids_and_input(self):
        data = {
            "computerList": [
                {
                    "id": 91,
                    "cpuPower": 0,
                    "memory": 0,
                    "networkBandwidth": 0,
                    "cost": 1,
                },
                {"id": 4, "cpuPower": 3, "memory": 3, "networkBandwidth": 3, "cost": 9},
            ],
            "processList": [
                {
                    "id": 820,
                    "requiredCpuPower": 1,
                    "requiredMemory": 1,
                    "requiredNetworkBandwidth": 1,
                    "computer": 91,
                },
                {
                    "id": -7,
                    "requiredCpuPower": 1,
                    "requiredMemory": 1,
                    "requiredNetworkBandwidth": 1,
                    "computer": None,
                },
            ],
            "score": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            original_text = json.dumps(data)
            path.write_text(original_text, encoding="utf-8")
            builder = DomainBuilder(path)
            domain = builder.build_domain_from_scratch()
            original_domain = deepcopy(domain)
            result = self.solve(domain)
            for initial in (domain, None):
                solved = builder.build_from_solution(result, initial)
                self.assertEqual(
                    {p.process_id: p.computer_id for p in solved.processes},
                    {820: 4, -7: 4},
                )
                self.assertEqual(solved.calculate_metrics()["soft_cost"], 9)
                self.assertIsNot(solved, domain)
            self.assertEqual(domain, original_domain)
            self.assertEqual(path.read_text(encoding="utf-8"), original_text)

    def test_reconstruction_rejects_incomplete_or_inconsistent_results(self):
        domain = make_domain([(3, 3, 3, 7)], [(1, 1, 1)])
        result = self.solve(domain)
        builder = DomainBuilder(Path("unused.json"))
        for broken in (
            replace(result, assignments={}),
            replace(result, assignments={100: 999}),
            replace(result, hard_penalty=100),
            replace(result, status="UNKNOWN", assignments=None),
        ):
            with self.subTest(result=broken), self.assertRaises(ValueError):
                builder.build_from_solution(broken, domain)

    def test_metrics_require_complete_assignments(self):
        domain = make_domain([(3, 3, 3, 7)], [(1, 1, 1)])
        with self.assertRaisesRegex(ValueError, "unassigned"):
            domain.calculate_metrics()

    def test_invalid_domains_fail_before_solving(self):
        valid = make_domain([(3, 3, 3, 7)], [(1, 1, 1)])
        invalid = [ScheduleCB([], valid.processes)]
        for target, field, value in (
            ("computer", "computer_id", True),
            ("computer", "cost", -1),
            ("computer", "memory_size", 1.5),
            ("computer", "cpu_power", "3"),
            ("process", "cpu_power_req", -1),
            ("process", "network_bandwidth_req", False),
            ("process", "computer_id", 99),
        ):
            domain = deepcopy(valid)
            entity = (
                domain.computers[0] if target == "computer" else domain.processes[0]
            )
            setattr(entity, field, value)
            invalid.append(domain)
        invalid.extend(
            [
                ScheduleCB(valid.computers * 2, valid.processes),
                ScheduleCB(valid.computers, valid.processes * 2),
            ]
        )
        for domain in invalid:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                CotwinBuilder().build_cotwin(domain)

    def test_integer_bound_failures_are_clear(self):
        for domain in (
            make_domain([(2**63, 0, 0, 1)], []),
            make_domain([(1, 1, 1, 2**40)], [(2**40, 0, 0)]),
        ):
            with (
                self.subTest(domain=domain),
                self.assertRaisesRegex(ValueError, "integer bounds"),
            ):
                CotwinBuilder().build_cotwin(domain)

    def test_malformed_json_is_rejected(self):
        for data in (
            [],
            {},
            {"computerList": {}, "processList": []},
            {"computerList": [None], "processList": []},
        ):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "bad.json"
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    DomainBuilder(path).build_domain_from_scratch()

    def test_first_fit_hints_are_complete_when_all_processes_fit(self):
        domain = make_domain([(2, 2, 2, 5), (3, 3, 3, 7)], [(1, 1, 1)] * 3)
        cotwin = CotwinBuilder().build_cotwin(domain)
        solver = cp_model.CpSolver()
        solver.parameters.fix_variables_to_their_hinted_value = True
        self.assertEqual(solver.solve(cotwin.model), cp_model.OPTIMAL)
        selected = {
            pid: next(cid for cid, variable in row.items() if solver.value(variable))
            for pid, row in cotwin.assignment_variables.items()
        }
        self.assertEqual(selected, {100: 10, 111: 10, 122: 17})

    def test_invalid_solver_settings(self):
        for options in (
            {"workers": 0},
            {"workers": True},
            {"no_improvement_seconds": 0},
            {"no_improvement_seconds": None},
            {"time_limit": -1},
            {"time_limit": float("nan")},
            {"time_limit": float("inf")},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                CloudBalancingSolver(**options)

    def test_watchdog_stops_search_without_callbacks_and_retries(self):
        stopped = threading.Event()
        solver = Mock()
        solver.stop_search.side_effect = stopped.set
        clock = SimpleNamespace(now=0)
        monitor = ScoreNoImprovement(solver, None, None, 15, clock=lambda: clock.now)
        monitor.start()
        try:
            clock.now = 16
            self.assertTrue(stopped.wait(2))
            self.assertTrue(monitor.timed_out)
            stopped.clear()
            self.assertTrue(stopped.wait(2))
        finally:
            monitor.close()
        self.assertFalse(monitor._thread.is_alive())

    def test_only_strict_integer_score_improvements_reset_idle_deadline(self):
        stopped = threading.Event()
        solver = Mock()
        solver.stop_search.side_effect = stopped.set
        clock = SimpleNamespace(now=0)
        monitor = ScoreNoImprovement(solver, None, None, 15, clock=lambda: clock.now)
        monitor.start()
        try:
            monitor.record_improvement((1, 2**53 + 4))
            clock.now = 10
            monitor.record_improvement((1, 2**53 + 3))
            clock.now = 16
            self.assertFalse(stopped.wait(0.15))
            monitor.record_improvement((1, 2**53 + 3))
            monitor.record_improvement((2, 0))
            clock.now = 26
            self.assertTrue(stopped.wait(2))
        finally:
            monitor.close()

    def test_total_time_limit_with_no_incumbent(self):
        domain = make_domain([(3, 3, 3, 7)], [(1, 1, 1)])
        result = CloudBalancingSolver(workers=1, time_limit=1e-9).solve(
            CotwinBuilder().build_cotwin(domain)
        )
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.termination_reason, "time_limit")
        self.assertIsNone(result.assignments)
        self.assertFalse(result.has_solution)
        self.assertFalse(
            any(
                t.name == "cloud-balancing-idle-watchdog" for t in threading.enumerate()
            )
        )

    def test_no_solution_statuses_do_not_read_variables(self):
        cotwin = CotwinBuilder().build_cotwin(make_domain([(3, 3, 3, 7)], [(1, 1, 1)]))
        for status in (cp_model.UNKNOWN, cp_model.INFEASIBLE, cp_model.MODEL_INVALID):
            with (
                self.subTest(status=status),
                patch(f"{SOLVER_MODULE}.cp_model.CpSolver") as factory,
            ):
                solver = factory.return_value
                solver.solve.return_value = status
                solver.status_name.return_value = status.name
                result = CloudBalancingSolver().solve(cotwin)
                self.assertFalse(result.has_solution)
                solver.value.assert_not_called()

    def test_watchdog_is_cleaned_up_when_solver_raises(self):
        cotwin = CotwinBuilder().build_cotwin(make_domain([(3, 3, 3, 7)], [(1, 1, 1)]))
        with patch(f"{SOLVER_MODULE}.cp_model.CpSolver") as factory:
            factory.return_value.solve.side_effect = RuntimeError("native failure")
            with self.assertRaisesRegex(RuntimeError, "native failure"):
                CloudBalancingSolver().solve(cotwin)
        self.assertFalse(
            any(
                t.name == "cloud-balancing-idle-watchdog" for t in threading.enumerate()
            )
        )

    def test_idle_timeout_is_reported_when_search_has_no_callbacks(self):
        cotwin = CotwinBuilder().build_cotwin(make_domain([(3, 3, 3, 7)], [(1, 1, 1)]))
        stopped = threading.Event()
        with patch(f"{SOLVER_MODULE}.cp_model.CpSolver") as factory:
            solver = factory.return_value
            solver.stop_search.side_effect = stopped.set

            def solve_without_callbacks(*args):
                if not stopped.wait(2):
                    self.fail("Idle watchdog did not stop a search without callbacks")
                return cp_model.UNKNOWN

            solver.solve.side_effect = solve_without_callbacks
            solver.status_name.return_value = "UNKNOWN"
            result = CloudBalancingSolver(no_improvement_seconds=0.01).solve(cotwin)
            self.assertEqual(result.termination_reason, "no_improvement")
            self.assertFalse(result.has_solution)
            solver.value.assert_not_called()
        self.assertFalse(
            any(
                t.name == "cloud-balancing-idle-watchdog" for t in threading.enumerate()
            )
        )

    def test_metrics_print_from_reconstructed_domain(self):
        domain = make_domain([(2, 2, 2, 7)], [(1, 1, 1)] * 2)
        solved = DomainBuilder(Path("unused.json")).build_from_solution(
            self.solve(domain), domain
        )
        with redirect_stdout(io.StringIO()) as output:
            solved.print_metrics()
        for text in (
            "Computer 10 utilization",
            "PIDs: 100, 111",
            "Total violations: 0",
            "Soft cost (used computers): 7",
        ):
            self.assertIn(text, output.getvalue())

    def test_direct_and_module_cli(self):
        data = {
            "computerList": [
                {"id": 41, "cpuPower": 1, "memory": 1, "networkBandwidth": 1, "cost": 7}
            ],
            "processList": [
                {
                    "id": 83,
                    "requiredCpuPower": 1,
                    "requiredMemory": 1,
                    "requiredNetworkBandwidth": 1,
                    "computer": None,
                }
            ],
            "score": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            for command, cwd in (
                ([sys.executable, str(SCRIPT)], directory),
                (
                    [
                        sys.executable,
                        "-m",
                        "examples.or_tools.cloud_balancing.scripts.solve_cloud_balancing",
                    ],
                    PROJECT_ROOT,
                ),
            ):
                with self.subTest(command=command):
                    result = subprocess.run(
                        command
                        + ["--input", str(path), "--workers", "1", "--time-limit", "2"],
                        cwd=cwd,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("New best solution #1:", result.stdout)
                    self.assertLess(
                        result.stdout.index("New best solution #1:"),
                        result.stdout.index("Solver status:"),
                    )
                    self.assertIn("Solver status: OPTIMAL", result.stdout)
                    self.assertIn("Soft cost (used computers): 7", result.stdout)
            missing = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(path.with_name("missing.json")),
                ],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(missing.returncode, 2)
            self.assertIn(
                "Select an existing JSON dataset with --input", missing.stderr
            )


if __name__ == "__main__":
    unittest.main()
