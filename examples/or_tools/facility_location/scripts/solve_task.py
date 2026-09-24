"""Generated domain -> CP-SAT cotwin -> reconstructed facility-location metrics."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0, help="Demo seed (default: 0)")
    parser.add_argument(
        "--workers", type=int, default=10, help="CP-SAT workers (default: 10)"
    )
    parser.add_argument(
        "--no-improvement-seconds",
        type=float,
        default=15,
        help="Stop after this many seconds without a better score (default: 15)",
    )
    parser.add_argument("--time-limit", type=float, help="Optional total search limit")
    parser.add_argument(
        "--mode",
        choices=("strict", "penalized"),
        default="strict",
        help="Capacity handling: strict (default) or penalized",
    )
    parser.add_argument(
        "--no-greedy-hints",
        action="store_true",
        help="Disable advisory greedy initialization hints",
    )
    args = parser.parse_args(argv)

    from examples.or_tools.facility_location.persistence.CotwinBuilder import (
        CotwinBuilder,
    )
    from examples.or_tools.facility_location.persistence.DomainBuilder import (
        DomainBuilder,
    )
    from examples.or_tools.facility_location.solver.FacilityLocationSolver import (
        FacilityLocationSolver,
    )

    try:
        solver = FacilityLocationSolver(
            args.workers, args.no_improvement_seconds, args.time_limit
        )
        domain_builder = DomainBuilder(seed=args.seed)
        domain = domain_builder.build_domain_from_scratch()
        print(
            f"Building model: {len(domain.facilities)} facilities, "
            f"{len(domain.consumers)} consumers",
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
        if not solution.has_solution:
            print("No assignment returned; business metrics are unavailable.")
            return 1
        solved_domain = domain_builder.build_from_solution(solution, domain)
        solved_domain.print_metrics()
    except (ValueError, OverflowError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
