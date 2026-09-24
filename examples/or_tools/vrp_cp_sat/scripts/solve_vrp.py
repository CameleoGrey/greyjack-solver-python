"""VRP file -> business domain -> CP-SAT cotwin -> reconstructed routes."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d2-n50-k10.vrp"
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d5-n500-k20.vrp"
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d8-n1000-k40.vrp"
#DEFAULT_INPUT = PROJECT_ROOT / "data" / "vehiclerouting" / "belgium-tw-d10-n2750-k55.vrp"
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="EUC_2D VRP file (default: checked-in 50-location dataset)",
    )
    parser.add_argument("--workers", type=int, default=10, help="CP-SAT workers")
    parser.add_argument(
        "--no-improvement-seconds",
        type=float,
        default=180,
        help="Stop after this long without a better score",
    )
    parser.add_argument(
        "--time-limit", type=float, help="Optional total search time limit in seconds"
    )
    parser.add_argument(
        "--no-greedy-hints",
        action="store_true",
        help="Disable the deterministic complete route hint",
    )
    parser.add_argument(
        "--plot", action="store_true", help="Show route plot (requires matplotlib)"
    )
    parser.add_argument(
        "--mode",
        choices=("penalized", "strict"),
        default="strict",
        help="Business constraints: penalized or strict (default)",
    )
    parser.add_argument(
        "--formulation",
        choices=("mtz", "circuit"),
        default="circuit",
        help="Route formulation: mtz (default) or circuit",
    )
    args = parser.parse_args(argv)

    # Keep --help usable before installing the optional solver dependency.
    from examples.or_tools.vrp_cp_sat.persistence.DomainBuilder import DomainBuilder
    from examples.or_tools.vrp_cp_sat.persistence.CotwinBuilder import CotwinBuilder
    from examples.or_tools.vrp_cp_sat.solver.VRPSolver import VRPSolver

    try:
        solver = VRPSolver(
            workers=args.workers,
            no_improvement_seconds=args.no_improvement_seconds,
            time_limit=args.time_limit,
        )
        builder = DomainBuilder(args.input)
        domain = builder.build_domain_from_scratch()
        print(
            f"Building {args.formulation.upper()} model: "
            f"{len(domain.customer_ids)} customers, "
            f"{len(domain.vehicles)} vehicles, {len(domain.depot_ids)} depots",
            flush=True,
        )
        cotwin = CotwinBuilder(
            use_greedy_hints=not args.no_greedy_hints,
            mode=args.mode,
            formulation=args.formulation,
        ).build_cotwin(domain)
        print(f"Mode: {args.mode}", flush=True)
        print(f"Solving with {args.workers} workers...", flush=True)
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
