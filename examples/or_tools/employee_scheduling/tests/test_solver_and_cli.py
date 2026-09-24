import io
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ortools.sat.python import cp_model

from examples.or_tools.employee_scheduling.domain.Employee import Employee
from examples.or_tools.employee_scheduling.domain.EmployeeSchedule import (
    EmployeeSchedule,
)
from examples.or_tools.employee_scheduling.domain.Shift import Shift
from examples.or_tools.employee_scheduling.persistence.CotwinBuilder import (
    CotwinBuilder,
)
from examples.or_tools.employee_scheduling.persistence.DomainBuilder import (
    DomainBuilder,
)
from examples.or_tools.employee_scheduling.scripts.solve_task import main
from examples.or_tools.employee_scheduling.solver.EmployeeSchedulingSolution import (
    EmployeeSchedulingSolution,
)
from examples.or_tools.employee_scheduling.solver.EmployeeSchedulingSolver import (
    EmployeeSchedulingSolver,
)
from examples.or_tools.employee_scheduling.solver.ScoreNoImprovement import (
    ScoreNoImprovement,
)


SOLVER_MODULE = "examples.or_tools.employee_scheduling.solver.EmployeeSchedulingSolver"
DOMAIN_BUILDER_MODULE = (
    "examples.or_tools.employee_scheduling.persistence.DomainBuilder"
)
CLI_MODULE = "examples.or_tools.employee_scheduling.scripts.solve_task"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = PROJECT_ROOT / "examples/or_tools/employee_scheduling/scripts/solve_task.py"
WATCHDOG_NAME = "employee-scheduling-idle-watchdog"


def tiny_domain(qualified=True):
    start = datetime(2026, 9, 28, 8)
    return EmployeeSchedule(
        [Employee("Alex", ["Nurse"] if qualified else [])],
        [Shift(71, start, start + timedelta(hours=1), "Ward", "Nurse")],
    )


class SolverLifecycleTests(unittest.TestCase):
    def assert_watchdog_closed(self):
        self.assertFalse(
            any(thread.name == WATCHDOG_NAME for thread in threading.enumerate())
        )

    def test_invalid_solver_settings(self):
        options = [{"workers": value} for value in (0, -1, True, 1.5)]
        options += [
            {"no_improvement_seconds": value}
            for value in (0, -1, None, True, float("nan"), float("inf"))
        ]
        options += [
            {"time_limit": value} for value in (0, -1, True, float("nan"), float("inf"))
        ]
        for setting in options:
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                EmployeeSchedulingSolver(**setting)

    def test_watchdog_stops_without_callbacks_and_retries(self):
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
        self.assert_watchdog_closed()

    def test_only_strict_integer_scores_reset_idle_deadline(self):
        stopped = threading.Event()
        solver = Mock()
        solver.stop_search.side_effect = stopped.set
        clock = SimpleNamespace(now=0)
        monitor = ScoreNoImprovement(solver, None, None, 15, clock=lambda: clock.now)
        monitor.start()
        try:
            with redirect_stdout(io.StringIO()) as output:
                monitor.record_improvement((1, 2**53 + 4))
                clock.now = 10
                monitor.record_improvement((1, 2**53 + 3))
                clock.now = 16
                self.assertFalse(stopped.wait(0.15))
                monitor.record_improvement((1, 2**53 + 3))
                monitor.record_improvement((2, -10000))
                clock.now = 26
                self.assertTrue(stopped.wait(2))
            self.assertEqual(output.getvalue().count("New best solution"), 2)
            self.assertIn(str(2**53 + 3), output.getvalue())
        finally:
            monitor.close()
        self.assert_watchdog_closed()

    def test_hard_improvement_resets_deadline_despite_worse_soft(self):
        stopped = threading.Event()
        solver = Mock()
        solver.stop_search.side_effect = stopped.set
        clock = SimpleNamespace(now=0)
        monitor = ScoreNoImprovement(solver, None, None, 15, clock=lambda: clock.now)
        monitor.start()
        try:
            with redirect_stdout(io.StringIO()):
                monitor.record_improvement((2, -1000))
                clock.now = 10
                monitor.record_improvement((1, 1000))
            clock.now = 16
            self.assertFalse(stopped.wait(0.15))
            clock.now = 26
            self.assertTrue(stopped.wait(2))
        finally:
            monitor.close()
        self.assert_watchdog_closed()

    def test_callback_reads_integer_components(self):
        hard, soft = object(), object()
        monitor = ScoreNoImprovement(Mock(), hard, soft, 15)
        with (
            patch.object(monitor, "value", side_effect=[3, 2**53 + 1]) as value,
            patch.object(monitor, "record_improvement") as record,
        ):
            monitor.on_solution_callback()
        self.assertEqual([call.args[0] for call in value.call_args_list], [hard, soft])
        record.assert_called_once_with((3, 2**53 + 1))

    def test_total_time_limit_with_no_incumbent(self):
        result = EmployeeSchedulingSolver(workers=1, time_limit=1e-9).solve(
            CotwinBuilder().build_cotwin(tiny_domain())
        )
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.termination_reason, "time_limit")
        self.assertIsNone(result.assignments)
        self.assertIsNone(result.hard_penalty)
        self.assertIsNone(result.soft_penalty_cents)
        self.assertFalse(result.has_solution)
        self.assertGreaterEqual(result.elapsed_seconds, 0)
        self.assert_watchdog_closed()

    def test_no_solution_statuses_do_not_read_native_values(self):
        cotwin = CotwinBuilder().build_cotwin(tiny_domain())
        for status in (cp_model.UNKNOWN, cp_model.INFEASIBLE, cp_model.MODEL_INVALID):
            with (
                self.subTest(status=status),
                patch(f"{SOLVER_MODULE}.cp_model.CpSolver") as factory,
            ):
                solver = factory.return_value
                solver.solve.return_value = status
                solver.status_name.return_value = status.name
                result = EmployeeSchedulingSolver().solve(cotwin)
                self.assertFalse(result.has_solution)
                self.assertIsNone(result.assignments)
                self.assertIsNone(result.hard_penalty)
                self.assertIsNone(result.soft_penalty_cents)
                solver.value.assert_not_called()
            self.assert_watchdog_closed()

    def test_watchdog_is_closed_when_native_solver_raises(self):
        cotwin = CotwinBuilder().build_cotwin(tiny_domain())
        with patch(f"{SOLVER_MODULE}.cp_model.CpSolver") as factory:
            factory.return_value.solve.side_effect = RuntimeError("native failure")
            with self.assertRaisesRegex(RuntimeError, "native failure"):
                EmployeeSchedulingSolver().solve(cotwin)
        self.assert_watchdog_closed()

    def test_idle_timeout_without_callbacks_is_reported(self):
        cotwin = CotwinBuilder().build_cotwin(tiny_domain())
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
            result = EmployeeSchedulingSolver(no_improvement_seconds=0.01).solve(cotwin)
            self.assertEqual(result.termination_reason, "no_improvement")
            self.assertFalse(result.has_solution)
            solver.value.assert_not_called()
        self.assert_watchdog_closed()

    def test_feasible_incumbent_is_preserved_at_time_limit(self):
        cotwin = CotwinBuilder().build_cotwin(tiny_domain())
        with patch(f"{SOLVER_MODULE}.cp_model.CpSolver") as factory:
            solver = factory.return_value
            solver.solve.return_value = cp_model.FEASIBLE
            solver.status_name.return_value = "FEASIBLE"
            solver.value.return_value = 0
            result = EmployeeSchedulingSolver(time_limit=1).solve(cotwin)
        self.assertTrue(result.has_solution)
        self.assertEqual(result.assignments, {71: 0})
        self.assertEqual(result.termination_reason, "time_limit")
        self.assert_watchdog_closed()


class CommandLineTests(unittest.TestCase):
    def test_direct_and_module_help_without_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            for command, cwd in (
                ([sys.executable, "-S", str(SCRIPT), "--help"], directory),
                ([sys.executable, "-S", "-m", CLI_MODULE, "--help"], PROJECT_ROOT),
            ):
                with self.subTest(command=command):
                    result = subprocess.run(
                        command, cwd=cwd, capture_output=True, text=True, timeout=15
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    for option in (
                        "--dataset-size",
                        "--seed",
                        "--start-date",
                        "--workers",
                        "--no-improvement-seconds",
                        "--time-limit",
                    ):
                        self.assertIn(option, result.stdout)

    def test_direct_and_module_cli_no_incumbent_path(self):
        with tempfile.TemporaryDirectory() as directory:
            for command, cwd in (
                ([sys.executable, str(SCRIPT)], directory),
                ([sys.executable, "-m", CLI_MODULE], PROJECT_ROOT),
            ):
                with self.subTest(command=command):
                    result = subprocess.run(
                        command
                        + [
                            "--dataset-size",
                            "small",
                            "--seed",
                            "37",
                            "--start-date",
                            "2026-09-28",
                            "--workers",
                            "1",
                            "--time-limit",
                            "1e-9",
                        ],
                        cwd=cwd,
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("15 employees, 139 shifts", result.stdout)
                    self.assertIn("Solver status: UNKNOWN", result.stdout)
                    self.assertIn("Termination reason: time_limit", result.stdout)
                    self.assertIn("No assignment returned", result.stdout)
                    self.assertNotIn("Business feasible:", result.stdout)

    def test_cli_passes_custom_configuration_and_prints_reconstructed_metrics(self):
        domain = tiny_domain()
        builder = Mock(wraps=DomainBuilder())
        builder.build_domain_from_scratch.return_value = domain
        with (
            patch(
                f"{DOMAIN_BUILDER_MODULE}.DomainBuilder", return_value=builder
            ) as factory,
            patch(
                f"{SOLVER_MODULE}.EmployeeSchedulingSolver",
                wraps=EmployeeSchedulingSolver,
            ) as solver_factory,
            redirect_stdout(io.StringIO()) as output,
        ):
            code = main(
                [
                    "--dataset-size",
                    "small",
                    "--seed",
                    "12",
                    "--start-date",
                    "2026-09-29",
                    "--workers",
                    "1",
                    "--no-improvement-seconds",
                    "2",
                    "--time-limit",
                    "3",
                ]
            )
        self.assertEqual(code, 0)
        factory.assert_called_once_with(
            random_seed=12, dataset_size="small", start_date=date(2026, 9, 29)
        )
        solver_factory.assert_called_once_with(
            workers=1, no_improvement_seconds=2, time_limit=3
        )
        builder.build_from_solution.assert_called_once()
        self.assertIs(
            builder.build_from_solution.call_args.kwargs["initial_domain"], domain
        )
        text = output.getvalue()
        self.assertLess(
            text.index("New best solution #1:"), text.index("Solver status:")
        )
        self.assertIn("Solver status: OPTIMAL", text)
        self.assertIn("Hard penalty: 0", text)
        self.assertIn("Soft penalty cents: 0", text)
        self.assertIn("Business feasible: True", text)
        self.assertIn("Alex", text)
        self.assertIsNone(domain.shifts[0].employee)

    def test_cli_reports_business_infeasibility_with_successful_solver_status(self):
        builder = Mock(wraps=DomainBuilder())
        builder.build_domain_from_scratch.return_value = tiny_domain(qualified=False)
        with (
            patch(f"{DOMAIN_BUILDER_MODULE}.DomainBuilder", return_value=builder),
            redirect_stdout(io.StringIO()) as output,
        ):
            code = main(["--mode", "penalized", "--workers", "1", "--time-limit", "3"])
        self.assertEqual(code, 0)
        self.assertIn("Solver status: OPTIMAL", output.getvalue())
        self.assertIn("Hard penalty: 1", output.getvalue())
        self.assertIn("Business feasible: False", output.getvalue())

    def test_cli_never_reconstructs_without_incumbent(self):
        builder = Mock(wraps=DomainBuilder())
        builder.build_domain_from_scratch.return_value = tiny_domain()
        missing = EmployeeSchedulingSolution(
            "UNKNOWN", None, None, None, 0.1, "no_improvement"
        )
        with (
            patch(f"{DOMAIN_BUILDER_MODULE}.DomainBuilder", return_value=builder),
            patch(f"{SOLVER_MODULE}.EmployeeSchedulingSolver") as solver_factory,
            redirect_stdout(io.StringIO()) as output,
        ):
            solver_factory.return_value.solve.return_value = missing
            code = main([])
        self.assertEqual(code, 1)
        builder.build_from_solution.assert_not_called()
        self.assertIn("No assignment returned", output.getvalue())

    def test_cli_invalid_arguments_exit_cleanly(self):
        for args in (
            ["--dataset-size", "medium"],
            ["--start-date", "2026-02-30"],
            ["--start-date", "9999-12-31"],
            ["--start-date", "2026-09-28T08:00:00"],
            ["--workers", "0"],
            ["--no-improvement-seconds", "nan"],
            ["--time-limit", "-1"],
        ):
            with (
                self.subTest(args=args),
                redirect_stderr(io.StringIO()) as errors,
                self.assertRaises(SystemExit) as raised,
            ):
                main(args)
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("error:", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())

    def test_standalone_workflow_never_imports_greyjack(self):
        program = """
import importlib.abc
import sys
from datetime import date
sys.path.insert(0, sys.argv[1])
class BlockGreyJack(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "greyjack" or fullname.startswith("greyjack."):
            raise AssertionError("Standalone example imported GreyJack: " + fullname)
sys.meta_path.insert(0, BlockGreyJack())
from examples.or_tools.employee_scheduling.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.employee_scheduling.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.employee_scheduling.solver.EmployeeSchedulingSolver import EmployeeSchedulingSolver
builder = DomainBuilder(random_seed=37, dataset_size="small", start_date=date(2026, 9, 28))
domain = builder.build_domain_from_scratch()
domain.shifts = domain.shifts[:1]
result = EmployeeSchedulingSolver(workers=1, time_limit=3).solve(CotwinBuilder().build_cotwin(domain))
assert result.has_solution
reconstructed = builder.build_from_solution(result, domain)
assert reconstructed.calculate_metrics()["hard_penalty"] == result.hard_penalty
assert not any(name == "greyjack" or name.startswith("greyjack.") for name in sys.modules)
print("Standalone round trip passed")
"""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-c", program, str(PROJECT_ROOT)],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Standalone round trip passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
