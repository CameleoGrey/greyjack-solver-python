# Facility location with Benders decomposition

This standalone OR-Tools example follows **business domain → cotwin → solver →
reconstructed business domain → independent metrics**. It reproduces the
`facility_location` demo and score without importing that package or GreyJack.
Python 3.12 or newer and OR-Tools are required.

## Run

From the repository root:

```bash
python -m pip install -r examples/or_tools/facility_location_benders/requirements.txt
python -m examples.or_tools.facility_location_benders.scripts.solve_task \
  --time-limit 30
```

Direct execution of `scripts/solve_task.py` works from any working directory.
The default seed generates the native 30-facility, 60-consumer London instance;
each facility has capacity 150 and each consumer has demand 15. The generator
does not change global random state. No download is needed.

| Option | Default | Meaning |
| --- | --- | --- |
| `--seed` | `0` | Demo data seed |
| `--mode` | `strict` | Strict capacity or penalized overload |
| `--workers` | `10` | CP-SAT master and integer-recourse workers |
| `--no-improvement-seconds` | `15` | Wall seconds since the last better complete assignment |
| `--time-limit` | None | Optional total wall-time limit |
| `--no-greedy-seed` | Off | Skip the initial greedy assignment |

The CLI exits 0 with an assignment, 1 without one, and 2 for invalid input.
`FEASIBLE` means that a complete assignment was replayed, but optimality remains
unproved. `UNKNOWN` means no assignment or proof was obtained. `OPTIMAL` and
`INFEASIBLE` require a completed master proof; neither follows from a timed-out
subproblem. An idle or total time limit can stop the search between Benders
iterations or during a master or integer-recourse solve.

The same flow is available through Python:

```python
from examples.or_tools.facility_location_benders.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.facility_location_benders.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.facility_location_benders.solver.FacilityLocationSolver import FacilityLocationSolver

builder = DomainBuilder(seed=0)
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
result = FacilityLocationSolver(time_limit=30).solve(cotwin)
if result.has_solution:
    solved = builder.build_from_solution(result, initial_domain=domain)
    solved.print_metrics()
```

## Model

The master uses one binary opening variable `y_f` per facility and a nonnegative
integer `theta` for assignment cost. Setup cost belongs to the master. The
fixed-opening subproblem assigns every consumer to exactly one facility and
requires `y_f = 1` exactly when at least one consumer uses that facility.
For strict mode it requires each load to stay within capacity. Penalized mode
allows overload and minimizes the weighted hard penalty before distance cost:

```text
distance_m = ceil(sqrt((latitude difference)^2 +
                       (longitude difference)^2) * 111000)
hard_penalty = sum(max(0, facility load - capacity))
soft_cost = 2 * sum(setup cost of used facilities)
          + 5 * sum(consumer-to-facility distance_m)
W = upper_bound(soft_cost) - lower_bound(soft_cost) + 1
master objective = 2 * sum(setup_cost_f * y_f) + theta
subproblem objective = W * hard_penalty + 5 * total_distance_m
```

The assignment LP supplies a dual affine lower bound on `theta`. The solver
rebuilds a rational feasible dual before adding an integer Benders cut. A cut
that exceeds safe CP-SAT integer limits is skipped. For equal positive demands
and compatible capacities, the LP is usually integral. For arbitrary supported
domains, an exact CP-SAT assignment subproblem resolves fractional LP results.
An exact subproblem result adds an opening-pattern cost cut; an exactly
infeasible pattern adds a no-good cut. These cuts make the finite opening search
exact even if some LP cuts are skipped.

The domain accepts the same custom cases as `facility_location`: varied or zero
nonnegative integer demands, nonnegative integer capacities, signed integer
setup costs, and sparse or negative integer IDs. Zero-demand consumers still
activate their chosen facility. The empty domain is supported. Model building
rejects unsafe integer bounds.

Each complete assignment is reconstructed into a copy of the business domain.
The domain recalculates usage, overload, setup, and distance; mismatched or
incomplete results are rejected. Every strictly better `(hard_penalty,
soft_cost)` score is printed and flushed. The idle clock starts at solve entry
and resets only for a better complete assignment. The `lower_bound` field is
reported only after a master solve has certified its current optimum.

Run tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/facility_location_benders/tests -v
```
