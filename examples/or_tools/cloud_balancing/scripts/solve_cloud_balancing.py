"""JSON -> business domain -> CP-SAT cotwin -> business solution -> metrics."""

import argparse
import sys
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_INPUT = (
    PROJECT_ROOT / "data" / "cloudbalancing" / "400computers-1200processes.json"
)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT, help="Cloud-balancing JSON dataset"
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="CP-SAT workers (default: 8)"
    )
    parser.add_argument(
        "--no-improvement-seconds",
        type=float,
        default=120,
        help="Stop after this many seconds without a better score (default: 120)",
    )
    parser.add_argument(
        "--time-limit", type=float, help="Optional total search time limit in seconds"
    )
    parser.add_argument(
        "--no-greedy-hints",
        action="store_true",
        help="Disable first-fit initialization hints",
    )
    parser.add_argument(
        "--mode", choices=("penalized", "strict"), default="strict",
        help="Business constraints: penalized (default) or strict",
    )
    args = parser.parse_args(argv)
    if not args.input.is_file():
        parser.error(
            f"Dataset not found: {args.input}. Select an existing JSON dataset with --input."
        )

    from examples.or_tools.cloud_balancing.persistence.DomainBuilder import (
        DomainBuilder,
    )
    from examples.or_tools.cloud_balancing.persistence.CotwinBuilder import (
        CotwinBuilder,
    )
    from examples.or_tools.cloud_balancing.solver.CloudBalancingSolver import (
        CloudBalancingSolver,
    )

    try:
        solver = CloudBalancingSolver(
            args.workers, args.no_improvement_seconds, args.time_limit
        )
        domain_builder = DomainBuilder(args.input)
        domain = domain_builder.build_domain_from_scratch()
        print(
            f"Building model: {len(domain.computers)} computers, {len(domain.processes)} processes",
            flush=True,
        )
        cotwin = CotwinBuilder(
            use_greed_init=not args.no_greedy_hints, mode=args.mode
        ).build_cotwin(domain)
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
        solved_domain.print_metrics()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
