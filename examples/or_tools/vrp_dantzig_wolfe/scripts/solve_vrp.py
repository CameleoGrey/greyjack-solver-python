"""VRP file -> domain -> Dantzig-Wolfe cotwin -> independently replayed routes."""

import argparse
import sys
from pathlib import Path
from time import monotonic


PROJECT_ROOT = Path(__file__).resolve().parents[4]
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d2-n50-k10.vrp"
DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d5-n500-k20.vrp"
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d8-n1000-k40.vrp"
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d10-n2750-k55.vrp"
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--mode", choices=("strict", "penalized"), default="strict")
    parser.add_argument("--time-limit", type=float, default=120)
    parser.add_argument("--pricing", choices=("fast", "exact"), default="fast")
    parser.add_argument("--seed-time-limit", type=float, default=10)
    parser.add_argument("--workers", type=int, default=10, help="CP-SAT seed workers")
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args(argv)

    # Keep --help usable without importing the optional OR-Tools dependency.
    from examples.or_tools.vrp_dantzig_wolfe.persistence.CotwinBuilder import (
        CotwinBuilder,
    )
    from examples.or_tools.vrp_dantzig_wolfe.persistence.DomainBuilder import (
        DomainBuilder,
    )
    from examples.or_tools.vrp_dantzig_wolfe.solver.VRPSolver import VRPSolver

    try:
        started = monotonic()
        builder = DomainBuilder(args.input)
        domain = builder.build_domain_from_scratch()
        cotwin = CotwinBuilder(mode=args.mode).build_cotwin(domain)
        print(
            f"Dantzig-Wolfe VRP: {len(cotwin.customer_ids)} customers, "
            f"{len(domain.vehicles)} vehicles, {len(cotwin.groups)} vehicle groups; "
            f"mode={args.mode}",
            flush=True,
        )
        result = VRPSolver(
            time_limit=args.time_limit - (monotonic() - started),
            seed_time_limit=args.seed_time_limit,
            workers=args.workers,
            use_seed=not args.no_seed,
            pricing_mode=args.pricing,
        ).solve(cotwin)
        print(f"Solver status: {result.status}")
        print(f"Termination reason: {result.termination_reason}")
        print(f"Root LP converged: {result.lp_converged}")
        print(f"Pricing status: {result.pricing_status}")
        print(f"Restricted master status: {result.restricted_master_status}")
        print(f"Generated columns: {result.column_count}")
        print(f"Generator best score: {result.generator_score}")
        print(f"Pool master score: {result.pool_master_score}")
        print(
            "Stage seconds: "
            f"generator={result.generator_seconds:.3f}, "
            f"pricing={result.pricing_seconds:.3f}, "
            f"master={result.master_seconds:.3f}"
        )
        print(f"Wall elapsed: {monotonic() - started:.3f} seconds")
        if not result.has_solution:
            print("No routes returned; business metrics are unavailable.")
            return 1
        solved = builder.build_from_solution(result, initial_domain=domain)
        solved.print_metrics()
        solved.print_paths()
        if args.plot:
            solved.plot_paths()
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
