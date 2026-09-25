"""Solve maintenance scheduling with exact logic-based Benders decomposition."""

import argparse
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-size", choices=("small", "large"), default="large")
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Planning-period start (default: first Monday on or after today)",
    )
    parser.add_argument("--mode", choices=("strict", "penalized"), default="penalized")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--no-improvement-seconds", type=float, default=60)
    parser.add_argument("--time-limit", type=float)
    args = parser.parse_args(argv)

    # Import OR-Tools only after parsing, so --help works without it installed.
    from examples.or_tools.maintenance_scheduling_benders.persistence import (
        CotwinBuilder,
        DomainBuilder,
    )
    from examples.or_tools.maintenance_scheduling_benders.solver import (
        MaintenanceSchedulingSolver,
    )

    try:
        builder = DomainBuilder(args.dataset_size, args.start_date)
        solver = MaintenanceSchedulingSolver(
            workers=args.workers,
            no_improvement_seconds=args.no_improvement_seconds,
            time_limit=args.time_limit,
        )
        domain = builder.build_domain_from_scratch()
        print(
            f"Building Benders model: {len(domain.crews)} crews, "
            f"{len(domain.jobs)} jobs, "
            f"{len(domain.work_calendar.work_day_list)} workdays",
            flush=True,
        )
        cotwin = CotwinBuilder(mode=args.mode).build_cotwin(domain)
        print(f"Mode: {args.mode}", flush=True)
        print(f"Solving with {args.workers} workers...", flush=True)
        solution = solver.solve(cotwin)
        print(f"Solver status: {solution.status}")
        print(f"Termination reason: {solution.termination_reason}")
        print(f"Benders iterations: {solution.iterations}")
        print(f"Master cuts: {solution.cuts}")
        print(f"Capacity cuts: {solution.capacity_cuts}")
        print(f"Subproblem cuts: {solution.subproblem_cuts}")
        print(f"Search elapsed: {solution.elapsed_seconds:.3f} seconds")
        if not solution.has_solution:
            print("No assignment returned; business metrics are unavailable.")
            return 1
        solved_domain = builder.build_from_solution(solution, initial_domain=domain)
        solved_domain.print_schedule()
        solved_domain.print_metrics()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
