"""TSP file -> business domain -> CP-SAT MTZ cotwin -> reconstructed tour."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = PROJECT_ROOT / "data" / "tsp"

# Checked-in datasets. Change DEFAULT_INPUT here or pass --input on the CLI.
#DEFAULT_INPUT = DATA_DIR / "dj38.tsp"
#DEFAULT_INPUT = DATA_DIR / "belgium-n50.tsp"
#DEFAULT_INPUT = DATA_DIR / "st70.tsp"
DEFAULT_INPUT = DATA_DIR / "belgium-n100.tsp"
#DEFAULT_INPUT = DATA_DIR / "pcb442.tsp"
#DEFAULT_INPUT = DATA_DIR / "belgium-n500.tsp"
#DEFAULT_INPUT = DATA_DIR / "lu980.tsp"
#DEFAULT_INPUT = DATA_DIR / "belgium-n1000.tsp"
#DEFAULT_INPUT = DATA_DIR / "belgium-n2750.tsp"
#DEFAULT_INPUT = DATA_DIR / "gr9882.tsp"
#DEFAULT_INPUT = DATA_DIR / "ch71009.tsp"
#DEFAULT_INPUT = DATA_DIR / "usa115475.tsp"

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="TSP input file (default: data/tsp/belgium-n50.tsp)",
    )
    parser.add_argument("--workers", type=int, default=10, help="CP-SAT workers")
    parser.add_argument(
        "--no-improvement-seconds",
        type=float,
        default=30,
        help="Stop after this many seconds without a better tour (default: 15)",
    )
    parser.add_argument(
        "--time-limit", type=float, help="Optional total search time limit in seconds"
    )
    parser.add_argument(
        "--no-greedy-hints",
        action="store_true",
        help="Disable the complete nearest-neighbor route hint",
    )
    parser.add_argument(
        "--plot", action="store_true", help="Show the tour plot (requires matplotlib)"
    )
    args = parser.parse_args(argv)

    # Keep --help available before the optional OR-Tools dependency is installed.
    from examples.or_tools.tsp_cp_sat.persistence.CotwinBuilder import CotwinBuilder
    from examples.or_tools.tsp_cp_sat.persistence.DomainBuilder import DomainBuilder
    from examples.or_tools.tsp_cp_sat.solver.TSPSolver import TSPSolver

    try:
        solver = TSPSolver(
            workers=args.workers,
            no_improvement_seconds=args.no_improvement_seconds,
            time_limit=args.time_limit,
        )
        builder = DomainBuilder(args.input)
        domain = builder.build_domain_from_scratch()
        print(f"Building MTZ model: {len(domain.locations_list) - 1} stops", flush=True)
        cotwin = CotwinBuilder(use_greedy_hints=not args.no_greedy_hints).build_cotwin(
            domain
        )
        print(f"Solving with {args.workers} workers...", flush=True)
        solution = solver.solve(cotwin)
        print(f"Solver status: {solution.status}")
        print(f"Termination reason: {solution.termination_reason}")
        print(f"Search elapsed: {solution.elapsed_seconds:.3f} seconds")
        if not solution.has_solution:
            print("No tour returned; business metrics are unavailable.")
            return 1
        solved = builder.build_from_solution(solution, initial_domain=domain)
        solved.print_metrics()
        solved.print_path()
        if args.plot:
            solved.plot_path()
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
