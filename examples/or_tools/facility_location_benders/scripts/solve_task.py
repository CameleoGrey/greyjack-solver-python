"""Generated domain -> Benders cotwin -> reconstructed facility metrics."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0, help="Demo seed (default: 0)")
    parser.add_argument("--mode", choices=("strict", "penalized"), default="strict")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--no-improvement-seconds", type=float, default=15)
    parser.add_argument("--time-limit", type=float)
    parser.add_argument("--no-greedy-seed", action="store_true")
    args = parser.parse_args(argv)

    # Keep --help usable before the optional OR-Tools dependency is installed.
    from examples.or_tools.facility_location_benders.persistence.CotwinBuilder import (
        CotwinBuilder,
    )
    from examples.or_tools.facility_location_benders.persistence.DomainBuilder import (
        DomainBuilder,
    )
    from examples.or_tools.facility_location_benders.solver.FacilityLocationSolver import (
        FacilityLocationSolver,
    )

    try:
        builder = DomainBuilder(seed=args.seed)
        domain = builder.build_domain_from_scratch()
        cotwin = CotwinBuilder(
            mode=args.mode, use_greedy_seed=not args.no_greedy_seed
        ).build_cotwin(domain)
        print(
            f"Building Benders model: {len(domain.facilities)} facilities, "
            f"{len(domain.consumers)} consumers",
            flush=True,
        )
        print(f"Mode: {args.mode}", flush=True)
        print(f"Solving with {args.workers} workers...", flush=True)
        result = FacilityLocationSolver(
            workers=args.workers,
            no_improvement_seconds=args.no_improvement_seconds,
            time_limit=args.time_limit,
        ).solve(cotwin)
        print(f"Solver status: {result.status}")
        print(f"Termination reason: {result.termination_reason}")
        print(f"Benders iterations: {result.iterations}")
        print(f"Optimality cuts: {result.optimality_cuts}")
        print(f"Feasibility cuts: {result.feasibility_cuts}")
        print(f"Certified lower bound: {result.lower_bound}")
        print(f"Search elapsed: {result.elapsed_seconds:.3f} seconds")
        if not result.has_solution:
            print("No assignment returned; business metrics are unavailable.")
            return 1
        solved = builder.build_from_solution(result, domain)
        solved.print_metrics()
    except (ValueError, OverflowError, RuntimeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
