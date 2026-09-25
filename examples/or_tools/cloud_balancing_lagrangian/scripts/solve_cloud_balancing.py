"""JSON -> Lagrangian cotwin -> replayed cloud-balancing assignment."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_INPUT = (
    PROJECT_ROOT / "data" / "cloudbalancing" / "400computers-1200processes.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--mode", choices=("strict", "penalized"), default="strict")
    parser.add_argument("--no-improvement-seconds", type=float, default=120)
    parser.add_argument("--time-limit", type=float)
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--no-greedy-seed", action="store_true")
    args = parser.parse_args(argv)
    if not args.input.is_file():
        parser.error(f"Dataset not found: {args.input}")

    from examples.or_tools.cloud_balancing_lagrangian.persistence.CotwinBuilder import (
        CotwinBuilder,
    )
    from examples.or_tools.cloud_balancing_lagrangian.persistence.DomainBuilder import (
        DomainBuilder,
    )
    from examples.or_tools.cloud_balancing_lagrangian.solver.CloudBalancingSolver import (
        CloudBalancingSolver,
    )

    try:
        builder = DomainBuilder(args.input)
        domain = builder.build_domain_from_scratch()
        print(
            f"Building Lagrangian cotwin: {len(domain.computers)} computers, "
            f"{len(domain.processes)} processes",
            flush=True,
        )
        cotwin = CotwinBuilder(
            mode=args.mode, use_greedy_seed=not args.no_greedy_seed
        ).build_cotwin(domain)
        print(
            f"Mode: {args.mode}; GLOP variables: {cotwin.model.NumVariables()}",
            flush=True,
        )
        result = CloudBalancingSolver(
            no_improvement_seconds=args.no_improvement_seconds,
            time_limit=args.time_limit,
            max_iterations=args.max_iterations,
        ).solve(cotwin)
        print(f"Solver status: {result.status}")
        print(f"Termination reason: {result.termination_reason}")
        print(f"Search elapsed: {result.elapsed_seconds:.3f} seconds")
        print(f"Dual iterations: {result.iterations}")
        if result.dual_lower_bound is not None:
            print(f"Dual lower bound: {result.dual_lower_bound}")
        if not result.has_solution:
            print("No assignment returned; business metrics are unavailable.")
            return 1
        solved = builder.build_from_solution(result, initial_domain=domain)
        solved.print_metrics()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
