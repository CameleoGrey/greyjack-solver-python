"""Solve the business-domain VRP with OR-Tools RoutingModel."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d2-n50-k10.vrp"
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d5-n500-k20.vrp"
DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d8-n1000-k40.vrp"
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d10-n2750-k55.vrp"

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="EUC_2D or EXPLICIT FULL_MATRIX VRP file",
    )
    parser.add_argument(
        "--no-improvement-seconds",
        type=float,
        default=15,
        help="Stop after this long without a better score (default: 15)",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=6000,
        help="Total search time limit in seconds (default: 6000)",
    )
    parser.add_argument(
        "--plot", default=True, action="store_true", help="Show routes using matplotlib"
    )
    parser.add_argument(
        "--mode", choices=("penalized", "strict"), default="strict",
        help="Business constraints: penalized (default) or strict",
    )
    args = parser.parse_args(argv)

    # Keep --help usable before installing the optional solver dependency.
    from examples.or_tools.vrp_routing_model.persistence.DomainBuilder import DomainBuilder
    from examples.or_tools.vrp_routing_model.persistence.CotwinBuilder import CotwinBuilder
    from examples.or_tools.vrp_routing_model.solver.VRPSolver import VRPSolver

    try:
        solver = VRPSolver(args.no_improvement_seconds, args.time_limit)
        builder = DomainBuilder(args.input)
        domain = builder.build_domain_from_scratch()
        print(
            f"Building RoutingModel: {len(domain.customer_ids)} customers, "
            f"{len(domain.vehicles)} vehicles, {len(domain.depot_ids)} depots",
            flush=True,
        )
        cotwin = CotwinBuilder(mode=args.mode).build_cotwin(domain)
        print(f"Mode: {args.mode}", flush=True)
        solution = solver.solve(cotwin)
        print(f"Solver status: {solution.status}")
        print(f"Termination reason: {solution.termination_reason}")
        print(f"Search elapsed: {solution.elapsed_seconds:.3f} seconds")
        if not solution.has_solution:
            print("No routes returned; business metrics are unavailable.")
            return 1
        solved = builder.build_from_solution(solution, initial_domain=domain)
        solved.print_metrics()
        solved.print_paths()
        if args.plot:
            solved.plot_paths()
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
