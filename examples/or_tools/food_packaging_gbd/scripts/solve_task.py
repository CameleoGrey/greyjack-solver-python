"""Generated food packaging -> GBD cotwin -> replayed business schedule."""

import argparse
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--line-count", type=int, default=5, help="Demo lines (default: 5)"
    )
    parser.add_argument(
        "--job-count", type=int, default=100, help="Demo jobs (default: 100)"
    )
    parser.add_argument("--seed", type=int, default=37, help="Demo seed (default: 37)")
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Planning start date (default: next Monday)",
    )
    parser.add_argument("--mode", choices=("strict", "penalized"), default="penalized")
    parser.add_argument("--workers", type=int, default=10, help="CP-SAT workers")
    parser.add_argument(
        "--no-improvement-seconds",
        type=float,
        default=180,
        help="Stop after this many seconds without a better schedule (default: 180)",
    )
    parser.add_argument("--time-limit", type=float, help="Optional total time limit")
    parser.add_argument(
        "--no-greedy-hints",
        action="store_true",
        help="Disable the deterministic initial schedule seed",
    )
    parser.add_argument(
        "--no-schedule",
        action="store_true",
        help="Print metrics without every job's line and production time",
    )
    args = parser.parse_args(argv)

    from examples.or_tools.food_packaging_gbd.persistence.CotwinBuilder import (
        CotwinBuilder,
    )
    from examples.or_tools.food_packaging_gbd.persistence.DomainBuilder import (
        DomainBuilder,
    )
    from examples.or_tools.food_packaging_gbd.solver.FoodPackagingSolver import (
        FoodPackagingSolver,
    )

    try:
        solver = FoodPackagingSolver(
            args.workers, args.no_improvement_seconds, args.time_limit
        )
        builder = DomainBuilder(
            args.line_count,
            args.job_count,
            seed=args.seed,
            start_date=args.start_date,
        )
        domain = builder.build_domain_from_scratch()
        print(
            f"Building model: {len(domain.products)} products, "
            f"{len(domain.lines)} lines, {len(domain.jobs)} jobs",
            flush=True,
        )
        cotwin = CotwinBuilder(
            mode=args.mode, use_greedy_hints=not args.no_greedy_hints
        ).build_cotwin(domain)
        print(f"Mode: {args.mode}", flush=True)
        print(f"Solving with {args.workers} workers...", flush=True)
        solution = solver.solve(cotwin)
        print(f"Solver status: {solution.status}")
        print(f"Termination reason: {solution.termination_reason}")
        print(f"Search elapsed: {solution.elapsed_seconds:.3f} seconds")
        print(
            f"GBD iterations: {solution.iterations}; dual cuts: {solution.gbd_cuts}; "
            f"pattern cuts: {solution.pattern_cuts}; feasibility cuts: "
            f"{solution.feasibility_cuts}; integer timing solves: "
            f"{solution.timing_solves}"
        )
        print(
            f"Certified hard lower bound: {solution.hard_lower_bound}; "
            f"certified cost lower bound: {solution.cost_lower_bound}"
        )
        if not solution.has_solution:
            print("No schedule returned; business metrics are unavailable.")
            return 1
        solved = builder.build_from_solution(solution, initial_domain=domain)
        if not args.no_schedule:
            solved.print_schedule()
        solved.print_metrics()
    except (ValueError, OverflowError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
