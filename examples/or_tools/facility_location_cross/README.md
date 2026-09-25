# Facility location with Cross decomposition

This standalone OR-Tools example keeps the business domain → cotwin → solver →
reconstructed business domain → independent metrics flow of `facility_location`.
It uses fixed-opening assignment recourse, capacity-priced assignment, and a
restricted dual master. A final exact CP-SAT search handles any remaining
integer gap. It imports no code from the other facility-location examples.

## Run

From the repository root:

```bash
python -m pip install -r examples/or_tools/facility_location_cross/requirements.txt
python -m examples.or_tools.facility_location_cross.scripts.solve_task --time-limit 30
```

Direct execution of `scripts/solve_task.py` also works. The default seed builds
the native 30-facility, 60-consumer London instance. Each facility has capacity
150, and each consumer has demand 15. No download is needed.

| Option | Default | Meaning |
| --- | --- | --- |
| `--seed` | `0` | Demo data seed |
| `--mode` | `strict` | Strict capacity or penalized overload |
| `--workers` | `10` | CP-SAT workers per solve |
| `--no-improvement-seconds` | `15` | Wall time since the last better complete business score |
| `--time-limit` | None | Optional total wall-time limit |
| `--no-greedy-seed` | Off | Skip the initial greedy assignment |

The same flow is available through Python:

```python
from examples.or_tools.facility_location_cross.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.facility_location_cross.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.facility_location_cross.solver.FacilityLocationSolver import FacilityLocationSolver

builder = DomainBuilder(seed=0)
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
result = FacilityLocationSolver(time_limit=30).solve(cotwin)
if result.has_solution:
    solved = builder.build_from_solution(result, initial_domain=domain)
    solved.print_metrics()
```

## Business model

Every consumer uses exactly one facility. A facility incurs setup cost exactly
when at least one consumer uses it; this also applies to zero-demand consumers.
The source distance uses the planar approximation in `Location`. For each
facility, `load` is the sum of its assigned consumer demands.

```text
hard_penalty = sum_f max(0, load_f - capacity_f)
soft_cost = 2 * sum_f(setup_cost_f if used_f else 0)
          + 5 * sum_c distance(c, assigned_facility_c)
```

Strict mode requires zero overload and minimizes `soft_cost`. Penalized mode
minimizes `(hard_penalty, soft_cost)` lexicographically, using the same checked
integer weight as the Benders example. Custom instances retain varied or zero
nonnegative demands, nonnegative capacities, signed setup costs, sparse integer
IDs, and empty domains. The cotwin rejects unsafe CP-SAT integer bounds.

## Cross decomposition

Let `y_f` indicate use, `x_cf` indicate assignment, and
`r_f = sum_c demand_c*x_cf - capacity_f*y_f`. The priced model keeps customer
coverage and the exact links `x_cf <= y_f <= sum_c x_cf`, but relaxes capacity.
For prices `mu_f >= 0`, it minimizes `soft_cost + sum_f mu_f*r_f`.
In penalized mode `mu_f <= W`, where `W` is the hard-score weight; minimizing
the Lagrangian over nonnegative overload then sets that overload to zero.
Prices are represented on a checked common integer scale in CP-SAT.

At each Cross iteration:

1. The priced solve proposes a complete assignment and opening pattern. A
   proved optimal priced solve also gives a valid lower bound.
2. The fixed-opening GLOP assignment LP supplies capacity prices and, when
   verified integral, an exact assignment for that pattern. Otherwise CP-SAT
   searches its integer recourse. Complete candidates are independently replayed.
3. A restricted GLOP dual master combines complete priced patterns and their
   capacity residuals. It reoptimizes prices to escape repeated patterns.
   Strict mode uses an artificial-overload phase before its cost phase.

The restricted master's objective is **not** reported as a global lower bound:
missing patterns can make it too high. Only a proved priced minimum supplies a
Lagrangian bound. The Cross loop reserves part of the time budget for a full
CP-SAT model, which can close a remaining integer gap or prove infeasibility.
Cross iterations, fixed-opening solves, priced solves, dual-master solves, and
distinct patterns are reported separately.

Every strictly better replayed `(hard_penalty, soft_cost)` is printed and
flushed immediately. Only such improvements reset the idle deadline; new
patterns or improved dual bounds do not. `OPTIMAL` requires a closed certified
bound or full CP-SAT proof. `INFEASIBLE` requires full CP-SAT proof. `FEASIBLE`
means a replayed assignment without global proof; `UNKNOWN` means neither an
assignment nor proof was obtained. The CLI exits 0 with an assignment, 1
without one, and 2 for invalid input.

## Verification

```bash
python -m unittest discover -s examples/or_tools/facility_location_cross/tests -v
```

The tests use small exhaustive oracles for proof checks. Normal launches use
the native generated instance. No performance advantage over Benders or the
monolithic CP-SAT example is assumed.
