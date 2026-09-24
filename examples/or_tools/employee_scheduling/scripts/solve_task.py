"""Demo data -> business domain -> CP-SAT cotwin -> business solution -> metrics."""

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
        "--dataset-size",
        choices=("small", "large"),
        default="large",
        help="Generated dataset size (default: large)",
    )
    parser.add_argument(
        "--seed", type=int, default=45, help="Demo-data random seed (default: 45)"
    )
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="First planning date (default: next Monday)",
    )
    parser.add_argument(
        "--workers", type=int, default=10, help="CP-SAT workers (default: 10)"
    )
    parser.add_argument(
        "--no-improvement-seconds",
        type=float,
        default=15,
        help="Stop after this many seconds without a better score (default: 15)",
    )
    parser.add_argument(
        "--time-limit", type=float, help="Optional total search time limit in seconds"
    )
    parser.add_argument(
        "--mode", choices=("penalized", "strict"), default="strict",
        help="Business constraints: penalized (default) or strict",
    )
    args = parser.parse_args(argv)

    # Keep --help usable before the standalone OR-Tools dependency is installed.
    from examples.or_tools.employee_scheduling.persistence.DomainBuilder import (
        DomainBuilder,
    )
    from examples.or_tools.employee_scheduling.persistence.CotwinBuilder import (
        CotwinBuilder,
    )
    from examples.or_tools.employee_scheduling.solver.EmployeeSchedulingSolver import (
        EmployeeSchedulingSolver,
    )

    try:
        solver = EmployeeSchedulingSolver(
            workers=args.workers,
            no_improvement_seconds=args.no_improvement_seconds,
            time_limit=args.time_limit,
        )
        domain_builder = DomainBuilder(
            random_seed=args.seed,
            dataset_size=args.dataset_size,
            start_date=args.start_date,
        )
        domain = domain_builder.build_domain_from_scratch()
        print(
            f"Building model: {len(domain.employees)} employees, "
            f"{len(domain.shifts)} shifts",
            flush=True,
        )
        cotwin = CotwinBuilder(mode=args.mode).build_cotwin(domain)
        print(f"Mode: {args.mode}", flush=True)
        print(f"Solving with {args.workers} workers...", flush=True)
        solution = solver.solve(cotwin)
        print(f"Solver status: {solution.status}")
        print(f"Termination reason: {solution.termination_reason}")
        print(f"Search elapsed: {solution.elapsed_seconds:.3f} seconds")
        if not solution.has_solution:
            print("No assignment returned; business metrics are unavailable.")
            return 1
        solved_domain = domain_builder.build_from_solution(
            solution, initial_domain=domain
        )
        solved_domain.print_schedule()
        solved_domain.print_metrics()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
