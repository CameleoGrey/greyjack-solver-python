import itertools
import io
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from examples.or_tools.vrp_dantzig_wolfe.domain import (
    Customer,
    Vehicle,
    VehicleRoutingPlan,
)
from examples.or_tools.vrp_dantzig_wolfe.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.vrp_dantzig_wolfe.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.vrp_dantzig_wolfe.solver.FastPricingSolver import (
    FastPricingSolver,
)
from examples.or_tools.vrp_dantzig_wolfe.solver.BestSolutionLogger import (
    BestSolutionLogger,
)
from examples.or_tools.vrp_dantzig_wolfe.solver.PricingSolver import (
    PriceResult,
    PricingSolver,
)
from examples.or_tools.vrp_dantzig_wolfe.solver.VRPSolution import VRPSolution
from examples.or_tools.vrp_dantzig_wolfe.solver.VRPSolver import VRPSolver
from examples.or_tools.vrp_dantzig_wolfe.solver.RoutePoolGenerator import (
    RoutePoolGenerator,
)
from examples.or_tools.vrp_dantzig_wolfe.solver.SeedSolver import SeedSolver


ROOT = Path(__file__).resolve().parents[4]
DATASET = ROOT / "data/vehiclerouting/belgium-tw-d2-n50-k10.vrp"


def small_domain(capacity: int = 7) -> VehicleRoutingPlan:
    return VehicleRoutingPlan(
        "small",
        [
            Customer(100, "D1", 0, 0, 0, 0, 12, 0),
            Customer(200, "D2", 0, 1, 0, 0, 12, 0),
            Customer(7, "A", 1, 0, 3, 0, 4, 2),
            Customer(9, "B", 1, 1, 4, 3, 7, 3),
            Customer(11, "C", 2, 0, 5, 5, 8, 2),
        ],
        [100, 200],
        [Vehicle(100, capacity, 0, 12), Vehicle(200, capacity, 0, 12)],
        [
            [0, 7, 2, 8, 4],
            [6, 0, 5, 2, 9],
            [3, 4, 0, 1, 3],
            [8, 3, 2, 0, 4],
            [5, 8, 2, 3, 0],
        ],
        True,
    )


def exhaustive_score(domain: VehicleRoutingPlan, strict: bool) -> tuple[int, int, int]:
    customers = [domain.location_by_id[i] for i in sorted(domain.customer_ids)]
    best = None
    for owners in itertools.product(range(len(domain.vehicles)), repeat=len(customers)):
        groups = [
            [customer for customer, owner in zip(customers, owners) if owner == vehicle]
            for vehicle in range(len(domain.vehicles))
        ]
        for routes in itertools.product(
            *(itertools.permutations(group) for group in groups)
        ):
            trial = deepcopy(domain)
            for vehicle, route in zip(trial.vehicles, routes):
                vehicle.customer_list = list(route)
            metrics = trial.calculate_metrics()
            score = tuple(
                metrics[name] for name in ("hard_penalty", "medium_penalty", "distance")
            )
            if strict and (score[0] or score[1]):
                continue
            if best is None or score < best:
                best = score
    return best


class DantzigWolfeTests(unittest.TestCase):
    def solve(self, domain, mode="strict", **kwargs):
        cotwin = CotwinBuilder(mode=mode).build_cotwin(domain)
        kwargs.setdefault("pricing_mode", "exact")
        with redirect_stdout(io.StringIO()):
            solution = VRPSolver(time_limit=10, seed_time_limit=1, **kwargs).solve(
                cotwin
            )
        return solution, cotwin

    def test_best_solution_logger_filters_and_flushes(self):
        calls = []
        times = iter((10.1, 10.2, 10.3))
        logger = BestSolutionLogger(
            10.0,
            clock=lambda: next(times),
            printer=lambda message, **kwargs: calls.append((message, kwargs)),
        )
        self.assertTrue(logger.record((2, 5, 10)))
        self.assertFalse(logger.record((2, 5, 10)))
        self.assertFalse(logger.record((2, 6, 1)))
        self.assertTrue(logger.record((2, 4, 50)))
        self.assertTrue(logger.record((1, 999, 999)))
        self.assertEqual(len(calls), 3)
        self.assertIn("[0.100s] New best solution #1", calls[0][0])
        self.assertIn("New best solution #2", calls[1][0])
        self.assertIn("New best solution #3", calls[2][0])
        self.assertTrue(all(kwargs == {"flush": True} for _, kwargs in calls))

    def test_solver_logs_global_best_and_final_score_matches(self):
        cotwin = CotwinBuilder(mode="strict").build_cotwin(small_domain())
        output = io.StringIO()
        with redirect_stdout(output):
            result = VRPSolver(time_limit=2, pricing_mode="exact").solve(cotwin)
        lines = [
            line
            for line in output.getvalue().splitlines()
            if "New best solution" in line
        ]
        self.assertTrue(lines)
        scores = []
        for expected_count, line in enumerate(lines, 1):
            match = re.fullmatch(
                r"\[\d+\.\d{3}s\] New best solution #(\d+): "
                r"hard_penalty=(\d+), medium_penalty=(\d+), distance=(\d+)",
                line,
            )
            self.assertIsNotNone(match, line)
            self.assertEqual(int(match.group(1)), expected_count)
            scores.append(tuple(int(match.group(i)) for i in (2, 3, 4)))
        self.assertTrue(all(left > right for left, right in zip(scores, scores[1:])))
        self.assertEqual(
            scores[-1],
            (result.hard_penalty, result.medium_penalty, result.distance),
        )

    def test_route_pool_and_master_forward_complete_scores(self):
        cotwin = CotwinBuilder(mode="strict").build_cotwin(small_domain())
        observed = []
        pool = RoutePoolGenerator.generate(
            cotwin,
            0.2,
            RoutePoolGenerator.STRATEGIES[0],
            on_solution=observed.append,
        )
        self.assertTrue(observed)
        self.assertEqual(min(observed), pool.best_score)
        master_scores = []
        result, status = VRPSolver._solve_integer_master(
            cotwin,
            monotonic() + 2,
            pool.best_routes,
            on_solution=master_scores.append,
        )
        self.assertIn(status, ("FEASIBLE", "OPTIMAL"))
        self.assertTrue(master_scores)
        self.assertEqual(master_scores[-1], min(master_scores))
        self.assertIsNotNone(result or pool.best_routes)

    def test_cp_sat_fallback_forwards_feasible_incumbents(self):
        locations = [Customer(100, "D", 0, 0, 0)] + [
            Customer(i, str(i), 0, i, 4 if i <= 3 else 6) for i in range(1, 7)
        ]
        matrix = [
            [
                0 if left == right else 1 if right in (1, 2, 3) else 100
                for right in range(7)
            ]
            for left in range(7)
        ]
        domain = VehicleRoutingPlan(
            "seed-fallback",
            locations,
            [100],
            [Vehicle(100, 10) for _ in range(3)],
            matrix,
            False,
        )
        cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
        self.assertFalse(SeedSolver._strict_valid(cotwin, SeedSolver.greedy(cotwin)))
        scores = []
        routes, proved_infeasible = SeedSolver().solve(
            cotwin, 2, 1, on_solution=scores.append
        )
        self.assertFalse(proved_infeasible)
        self.assertIsNotNone(routes)
        self.assertTrue(scores)
        self.assertEqual(scores[-1][:2], (0, 0))

    def test_no_complete_assignment_emits_no_best_line(self):
        domain = VehicleRoutingPlan(
            "impossible",
            [Customer(100, "D", 0, 0, 0), Customer(7, "A", 0, 1, 3)],
            [100],
            [Vehicle(100, 2)],
            [[0, 4], [7, 0]],
            False,
        )
        cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
        output = io.StringIO()
        with redirect_stdout(output):
            result = VRPSolver(time_limit=1).solve(cotwin)
        self.assertFalse(result.has_solution)
        self.assertNotIn("New best solution", output.getvalue())

    def test_strict_and_penalized_match_small_exhaustive_search(self):
        for mode, capacity in (("strict", 7), ("penalized", 5)):
            with self.subTest(mode=mode):
                domain = small_domain(capacity)
                solution, cotwin = self.solve(domain, mode)
                self.assertTrue(solution.has_solution)
                self.assertTrue(solution.lp_converged)
                self.assertEqual(solution.restricted_master_status, "OPTIMAL")
                self.assertEqual(
                    (solution.hard_penalty, solution.medium_penalty, solution.distance),
                    exhaustive_score(domain, mode == "strict"),
                )
                reconstructed = DomainBuilder("unused").build_from_solution(
                    solution, domain
                )
                self.assertEqual(
                    sum(
                        len(vehicle.customer_list) for vehicle in reconstructed.vehicles
                    ),
                    3,
                )
                self.assertTrue(
                    all(not vehicle.customer_list for vehicle in domain.vehicles)
                )
                self.assertEqual(len(cotwin.groups), 2)

    def test_no_seed_uses_artificial_columns_and_exact_pricing(self):
        domain = VehicleRoutingPlan(
            "one",
            [Customer(100, "D", 0, 0, 0), Customer(7, "A", 0, 1, 2)],
            [100],
            [Vehicle(100, 2)],
            [[0, 4], [7, 0]],
            False,
        )
        solution, cotwin = self.solve(domain, use_seed=False)
        self.assertTrue(solution.has_solution)
        self.assertTrue(solution.lp_converged)
        self.assertEqual(solution.distance, 11)
        self.assertEqual(solution.routes, ((7,),))
        self.assertEqual(len(cotwin.columns), 1)

    def test_identical_vehicle_group_can_use_two_routes(self):
        domain = VehicleRoutingPlan(
            "two-routes",
            [
                Customer(100, "D", 0, 0, 0),
                Customer(7, "A", 0, 1, 2),
                Customer(9, "B", 1, 0, 2),
            ],
            [100],
            [Vehicle(100, 2), Vehicle(100, 2)],
            [[0, 4, 3], [5, 0, 1], [6, 1, 0]],
            False,
        )
        solution, cotwin = self.solve(domain)
        self.assertEqual(len(cotwin.groups), 1)
        self.assertEqual(set(solution.routes), {(7,), (9,)})
        self.assertEqual(solution.distance, 18)

    def test_pricing_excludes_disconnected_zero_service_cycle(self):
        domain = VehicleRoutingPlan(
            "cycle",
            [Customer(100, "D", 0, 0, 0)]
            + [Customer(i, str(i), 0, i, 0) for i in (1, 2, 3)],
            [100],
            [Vehicle(100, 1)],
            [[0, 100, 100, 100]] + [[100, 0, 0, 0] for _ in range(3)],
            False,
        )
        solution, _ = self.solve(domain, use_seed=False)
        self.assertEqual(set(solution.routes[0]), {1, 2, 3})
        self.assertEqual(solution.distance, 200)

    def test_pricing_reduced_cost_and_grouping(self):
        domain = VehicleRoutingPlan(
            "one",
            [Customer(100, "D", 0, 0, 0), Customer(7, "A", 0, 1, 2)],
            [100],
            [Vehicle(100, 2), Vehicle(100, 2)],
            [[0, 4], [7, 0]],
            False,
        )
        cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
        self.assertEqual(len(cotwin.groups), 1)
        result = PricingSolver().price(cotwin, 0, {7: 15}, 0, (0, 0, 1), 2)
        self.assertTrue(result.optimal)
        self.assertEqual(result.column.customers, (7,))
        self.assertAlmostEqual(result.reduced_cost, -4)

    def test_fast_pricing_validates_reduced_cost(self):
        domain = VehicleRoutingPlan(
            "one",
            [Customer(100, "D", 0, 0, 0), Customer(7, "A", 0, 1, 2)],
            [100],
            [Vehicle(100, 2)],
            [[0, 4], [7, 0]],
            False,
        )
        cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
        routes = FastPricingSolver.price(cotwin, 0, {7: 15}, 0, (0, 0, 1), 0.1)
        self.assertTrue(routes)
        self.assertEqual(routes[0].column.customers, (7,))
        self.assertAlmostEqual(routes[0].reduced_cost, -4)
        self.assertFalse(routes[0].optimal)

    def test_fast_pricing_keeps_time_window_semantics(self):
        duals = {7: 30.0, 9: 30.0, 11: 30.0}
        for mode, components in (
            ("strict", (0.0, 0.0, 1.0)),
            ("penalized", (1.0, 2.0, 1.0)),
        ):
            with self.subTest(mode=mode):
                cotwin = CotwinBuilder(mode=mode).build_cotwin(small_domain(5))
                routes = FastPricingSolver.price(cotwin, 0, duals, 0.0, components, 0.1)
                self.assertTrue(routes)
                for result in routes:
                    column = cotwin.make_column(0, result.column.customers)
                    self.assertAlmostEqual(
                        result.reduced_cost,
                        sum(a * b for a, b in zip(components, column.score))
                        - sum(duals[c] for c in column.customers),
                    )
                    if mode == "strict":
                        self.assertEqual(column.score[:2], (0, 0))

    def test_route_pool_collects_complete_assignments(self):
        domain = small_domain()
        cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
        pool = RoutePoolGenerator.generate(
            cotwin, 0.2, RoutePoolGenerator.STRATEGIES[0]
        )
        self.assertIsNotNone(pool.best_routes)
        self.assertGreater(pool.solutions, 0)
        self.assertGreater(len(cotwin.columns), 0)
        self.assertEqual(
            pool.best_score,
            VRPSolver._score_routes(
                cotwin,
                pool.best_routes,
                {
                    vehicle: group_index
                    for group_index, group in enumerate(cotwin.groups)
                    for vehicle in group.vehicle_indices
                },
            ),
        )

    def test_fast_mode_keeps_incumbent_without_lp_proof(self):
        result, _ = self.solve(small_domain(), pricing_mode="fast")
        self.assertTrue(result.has_solution)
        self.assertFalse(result.lp_converged)
        self.assertEqual(result.pricing_mode, "fast")
        self.assertIsNotNone(result.generator_score)
        self.assertIsNotNone(result.pool_master_score)
        self.assertLessEqual(
            (result.hard_penalty, result.medium_penalty, result.distance),
            result.generator_score,
        )

    def test_pricing_matches_exhaustive_elementary_routes(self):
        duals = {7: 2.5, 9: -1.0, 11: 5.25}
        for mode, components in (
            ("strict", (0.0, 0.0, 1.0)),
            ("penalized", (0.7, 0.3, 1.2)),
        ):
            with self.subTest(mode=mode):
                cotwin = CotwinBuilder(mode=mode).build_cotwin(small_domain(5))
                expected = float("inf")
                for count in range(1, len(cotwin.customer_ids) + 1):
                    for route in itertools.permutations(cotwin.customer_ids, count):
                        try:
                            column = cotwin.make_column(0, route)
                        except ValueError:
                            continue
                        reduced = (
                            sum(a * b for a, b in zip(components, column.score))
                            - sum(duals[c] for c in route)
                            + 1.5
                        )
                        expected = min(expected, reduced)
                result = PricingSolver().price(cotwin, 0, duals, -1.5, components, 5)
                self.assertTrue(result.optimal)
                self.assertAlmostEqual(result.reduced_cost, expected)

    def test_strict_infeasibility_and_penalized_scores(self):
        domain = VehicleRoutingPlan(
            "unavoidable",
            [
                Customer(100, "D", 0, 0, 0, 0, 10, 0),
                Customer(7, "A", 0, 1, 3, 0, 1, 2),
            ],
            [100],
            [Vehicle(100, 2, 0, 10)],
            [[0, 4], [7, 0]],
            True,
        )
        strict, _ = self.solve(domain)
        self.assertEqual(strict.status, "INFEASIBLE")
        self.assertFalse(strict.has_solution)
        penalized, _ = self.solve(domain, "penalized")
        self.assertEqual(
            (penalized.hard_penalty, penalized.medium_penalty, penalized.distance),
            (1, 1, 11),
        )
        penalized_fast, _ = self.solve(domain, "penalized", pricing_mode="fast")
        self.assertEqual(
            (
                penalized_fast.hard_penalty,
                penalized_fast.medium_penalty,
                penalized_fast.distance,
            ),
            (1, 1, 11),
        )
        no_seed, _ = self.solve(domain, use_seed=False)
        self.assertEqual(no_seed.status, "INFEASIBLE")
        self.assertEqual(no_seed.termination_reason, "phase_one_proved_infeasible")

    def test_unsafe_numeric_bounds_are_rejected(self):
        domain = VehicleRoutingPlan(
            "large",
            [Customer(100, "D", 0, 0, 0), Customer(7, "A", 0, 1, 1)],
            [100],
            [Vehicle(100, 1)],
            [[0, 2**61], [2**61, 0]],
            False,
        )
        with self.assertRaisesRegex(ValueError, "numeric bounds"):
            CotwinBuilder(mode="strict").build_cotwin(domain)

    def test_incomplete_pricing_does_not_claim_convergence(self):
        domain = VehicleRoutingPlan(
            "one",
            [Customer(100, "D", 0, 0, 0), Customer(7, "A", 0, 1, 2)],
            [100],
            [Vehicle(100, 2)],
            [[0, 4], [7, 0]],
            False,
        )
        with patch.object(
            PricingSolver,
            "price",
            return_value=PriceResult(None, None, False, "UNKNOWN"),
        ):
            result, _ = self.solve(domain)
        self.assertTrue(result.has_solution)
        self.assertFalse(result.lp_converged)
        self.assertEqual(result.pricing_status, "PRICING_INCOMPLETE")
        self.assertEqual(result.restricted_master_status, "OPTIMAL")
        self.assertEqual(result.status, "FEASIBLE")

    def test_replay_rejects_wrong_solver_score(self):
        domain = small_domain()
        with self.assertRaisesRegex(ValueError, "differ"):
            DomainBuilder("unused").build_from_solution(
                VRPSolution("FEASIBLE", ((7, 9), (11,)), 0, 0, 0, 0, "test"),
                domain,
            )

    def test_checked_in_parser_and_cli(self):
        domain = DomainBuilder(DATASET).build_domain_from_scratch()
        self.assertEqual(
            (len(domain.locations), len(domain.customer_ids), len(domain.vehicles)),
            (50, 48, 10),
        )
        self.assertEqual(domain.depot_ids, [782, 1655])
        self.assertEqual(
            len(CotwinBuilder(mode="strict").build_cotwin(domain).groups), 2
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tiny-k1.vrp"
            path.write_text(
                "NAME: tiny-k1\nTYPE: CVRPTW\nDIMENSION: 2\n"
                "EDGE_WEIGHT_TYPE: EUC_2D\nCAPACITY: 3\nNODE_COORD_SECTION\n"
                "100 0 0 D\n10 0 1 A\nDEMAND_SECTION\n"
                "100 0 0 20 0\n10 2 0 10 1\n"
                "DEPOT_SECTION\n100\n-1\nEOF\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "examples.or_tools.vrp_dantzig_wolfe.scripts.solve_vrp",
                    "--input",
                    str(path),
                    "--time-limit",
                    "5",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Root LP converged: False", result.stdout)
            self.assertIn("Unique stops (excluding depots): 1", result.stdout)
            exact = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "examples.or_tools.vrp_dantzig_wolfe.scripts.solve_vrp",
                    "--input",
                    str(path),
                    "--time-limit",
                    "5",
                    "--pricing",
                    "exact",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(exact.returncode, 0, exact.stderr)
            self.assertIn("Root LP converged: True", exact.stdout)


if __name__ == "__main__":
    unittest.main()
