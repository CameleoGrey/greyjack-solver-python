import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from ortools.linear_solver import pywraplp

from examples.or_tools.cloud_balancing_lagrangian.domain.Computer import Computer
from examples.or_tools.cloud_balancing_lagrangian.domain.Process import Process
from examples.or_tools.cloud_balancing_lagrangian.domain.ScheduleCB import ScheduleCB
from examples.or_tools.cloud_balancing_lagrangian.persistence.CotwinBuilder import (
    CotwinBuilder,
)
from examples.or_tools.cloud_balancing_lagrangian.persistence.DomainBuilder import (
    DomainBuilder,
)
from examples.or_tools.cloud_balancing_lagrangian.solver.CloudBalancingSolver import (
    CloudBalancingSolver,
)
from examples.or_tools.cloud_balancing_lagrangian.solver.ScoreNoImprovement import (
    ScoreNoImprovement,
)


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (
    ROOT
    / "examples/or_tools/cloud_balancing_lagrangian/scripts/solve_cloud_balancing.py"
)


def make_domain(computers, processes):
    return ScheduleCB(
        [Computer(10 + 7 * i, *values) for i, values in enumerate(computers)],
        [Process(100 + 11 * i, *values) for i, values in enumerate(processes)],
    )


def independent_score(domain, assignment):
    hard = 0
    soft = 0
    for computer in domain.computers:
        assigned = [
            p
            for p in domain.processes
            if assignment[p.process_id] == computer.computer_id
        ]
        if assigned:
            soft += computer.cost
        for r in range(3):
            hard += max(
                0,
                sum(p.requirements[r] for p in assigned) - computer.resources[r],
            )
    return hard, soft


def exact_optimum(domain, mode):
    process_ids = [p.process_id for p in domain.processes]
    computer_ids = [c.computer_id for c in domain.computers]
    scores = (
        independent_score(domain, dict(zip(process_ids, chosen)))
        for chosen in itertools.product(computer_ids, repeat=len(process_ids))
    )
    if mode == "strict":
        scores = (score for score in scores if score[0] == 0)
    return min(scores, default=None)


class CloudBalancingLagrangianTests(unittest.TestCase):
    def solve(self, domain, mode="strict", *, max_iterations=20):
        cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
        with redirect_stdout(StringIO()):
            result = CloudBalancingSolver(
                no_improvement_seconds=2, max_iterations=max_iterations
            ).solve(cotwin)
        return cotwin, result

    def test_small_cases_have_valid_replayed_incumbents_and_dual_bounds(self):
        cases = [
            ([(1, 1, 1, 7)], [(1, 1, 1)]),
            ([(1, 1, 1, 1), (2, 2, 2, 5)], [(1, 1, 1)] * 2),
            ([(0, 0, 0, 7)], [(1, 2, 3)]),
            ([(0, 0, 0, 0), (0, 0, 0, 3)], [(0, 0, 0)]),
        ]
        for computers, processes in cases:
            for mode in ("strict", "penalized"):
                with self.subTest(computers=computers, processes=processes, mode=mode):
                    domain = make_domain(computers, processes)
                    optimum = exact_optimum(domain, mode)
                    cotwin, result = self.solve(domain, mode)
                    if optimum is None:
                        self.assertFalse(result.has_solution)
                        self.assertIn(result.status, ("INFEASIBLE", "UNKNOWN"))
                        continue
                    self.assertTrue(result.has_solution)
                    score = independent_score(domain, result.assignments)
                    self.assertEqual(score, (result.hard_penalty, result.soft_cost))
                    self.assertGreaterEqual(score, optimum)
                    if result.dual_lower_bound is not None:
                        upper = (
                            optimum[1]
                            if mode == "strict"
                            else cotwin.hard_weight * optimum[0] + optimum[1]
                        )
                        self.assertLessEqual(result.dual_lower_bound, upper)
                    self.assertEqual(domain.processes[0].computer_id, None)

    def test_glop_model_matches_separable_dual_formula(self):
        domain = make_domain(
            [(2, 2, 2, 4), (3, 3, 3, 7)], [(1, 1, 1)] * 3 + [(2, 0, 1)]
        )
        cotwin = CotwinBuilder(mode="penalized").build_cotwin(domain)
        self.assertEqual(len(cotwin.groups), 2)
        self.assertEqual(cotwin.model.NumVariables(), 6)
        mu = {10: [1.25, 0.5, 2.0], 17: [0.25, 1.5, 0.75]}
        lam = {10: 0.75, 17: 1.25}
        CloudBalancingSolver._set_relaxed_objective(cotwin, mu, lam)
        self.assertEqual(cotwin.model.Solve(), pywraplp.Solver.OPTIMAL)
        exact = CloudBalancingSolver._dual_value_exact(cotwin, mu, lam)
        self.assertAlmostEqual(cotwin.model.Objective().Value(), float(exact))
        optimum = exact_optimum(domain, "penalized")
        self.assertLessEqual(exact, cotwin.hard_weight * optimum[0] + optimum[1])

    def test_tied_relaxed_choices_give_balanced_ascent_direction(self):
        domain = make_domain([(0, 0, 0, 1)] * 2, [(1, 0, 0)])
        cotwin = CotwinBuilder(mode="penalized").build_cotwin(domain)
        mu = {10: [0.0, 0.0, 0.0], 17: [0.0, 0.0, 0.0]}
        lam = {10: 1.0, 17: 1.0}
        CloudBalancingSolver._set_relaxed_objective(cotwin, mu, lam)
        self.assertEqual(cotwin.model.Solve(), pywraplp.Solver.OPTIMAL)
        capacity, activation = CloudBalancingSolver._subgradients(cotwin, mu, lam)
        self.assertEqual((capacity[10][0], capacity[17][0]), (0.5, 0.5))
        self.assertEqual((activation[10], activation[17]), (0.0, 0.0))

    def test_certified_gap_can_prove_optimality(self):
        _, result = self.solve(make_domain([(1, 1, 1, 7)], [(1, 1, 1)]))
        self.assertEqual(result.status, "OPTIMAL")
        self.assertEqual(result.termination_reason, "optimal")
        self.assertEqual((result.hard_penalty, result.soft_cost), (0, 7))
        self.assertGreater(result.dual_lower_bound, Decimal(6))
        self.assertLessEqual(result.dual_lower_bound, Decimal(7))

    def test_strict_unresolved_case_is_not_called_infeasible(self):
        domain = make_domain([(3, 3, 3, 4)] * 2, [(2, 2, 2)] * 3)
        _, result = self.solve(domain, max_iterations=2)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.termination_reason, "iteration_limit")
        self.assertIsNone(result.assignments)
        self.assertIsNone(exact_optimum(domain, "strict"))
        cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
        with redirect_stdout(StringIO()):
            idle = CloudBalancingSolver(no_improvement_seconds=0.02).solve(cotwin)
        self.assertEqual(
            (idle.status, idle.termination_reason), ("UNKNOWN", "no_improvement")
        )

    def test_reconstruction_preserves_ids_and_source_data(self):
        data = {
            "computerList": [
                {
                    "id": 91,
                    "cpuPower": 0,
                    "memory": 0,
                    "networkBandwidth": 0,
                    "cost": 1,
                },
                {
                    "id": -4,
                    "cpuPower": 3,
                    "memory": 3,
                    "networkBandwidth": 3,
                    "cost": 9,
                },
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
            path.write_text(json.dumps(data), encoding="utf-8")
            builder = DomainBuilder(path)
            domain = builder.build_domain_from_scratch()
            original = deepcopy(domain)
            _, result = self.solve(domain)
            solved = builder.build_from_solution(result, initial_domain=domain)
            self.assertEqual(
                (
                    solved.calculate_metrics()["hard_penalty"],
                    solved.calculate_metrics()["soft_cost"],
                ),
                (result.hard_penalty, result.soft_cost),
            )
            self.assertEqual(domain, original)
            self.assertEqual(path.read_text(encoding="utf-8"), json.dumps(data))

    def test_empty_and_invalid_inputs(self):
        empty = ScheduleCB([], [])
        _, result = self.solve(empty)
        self.assertEqual((result.status, result.assignments), ("OPTIMAL", {}))
        with self.assertRaisesRegex(ValueError, "Cannot assign"):
            CotwinBuilder().build_cotwin(make_domain([], [(1, 1, 1)]))
        with self.assertRaisesRegex(ValueError, "numeric bounds"):
            CotwinBuilder().build_cotwin(make_domain([(1, 1, 1, 2**63)], [(1, 1, 1)]))
        huge_cost = make_domain([(1, 1, 1, 2**60)], [(1, 1, 1)])
        _, huge_result = self.solve(huge_cost, max_iterations=1)
        self.assertEqual(huge_result.soft_cost, 2**60)
        with self.assertRaisesRegex(ValueError, "mode"):
            CotwinBuilder(mode="other")
        with self.assertRaisesRegex(ValueError, "max_iterations"):
            CloudBalancingSolver(max_iterations=0)

    def test_logger_resets_only_for_strict_improvements_and_flushes(self):
        ticks = iter((1.0, 2.0))
        logger = ScoreNoImprovement(0, 5, clock=lambda: next(ticks))
        with patch("builtins.print") as output:
            self.assertTrue(logger.record((1, 9), {1: 10}))
            self.assertFalse(logger.record((1, 9), {1: 20}))
            self.assertFalse(logger.record((2, 1), {1: 20}))
            self.assertTrue(logger.record((0, 20), {1: 20}))
        self.assertEqual(logger.deadline, 7)
        self.assertEqual(logger.best_assignments, {1: 20})
        self.assertEqual(logger.sequence, 2)
        self.assertTrue(all(call.kwargs["flush"] for call in output.call_args_list))

    def test_idle_limit_and_direct_cli(self):
        domain = make_domain([(1, 1, 1, 7)], [(1, 1, 1)])
        cotwin = CotwinBuilder(mode="penalized").build_cotwin(domain)
        with redirect_stdout(StringIO()):
            result = CloudBalancingSolver(no_improvement_seconds=0.001).solve(cotwin)
        self.assertTrue(result.has_solution)
        self.assertIn(result.termination_reason, ("optimal", "no_improvement"))

        command = [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(ROOT / "data/cloudbalancing/2computers-6processes.json"),
            "--max-iterations",
            "2",
            "--no-improvement-seconds",
            "2",
        ]
        completed = subprocess.run(
            command,
            cwd=tempfile.gettempdir(),
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("New best solution", completed.stdout)
        self.assertIn("Resource feasible: True", completed.stdout)


if __name__ == "__main__":
    unittest.main()
