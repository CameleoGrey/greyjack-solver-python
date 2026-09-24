# Facility location with OR-Tools

This standalone CP-SAT example preserves the source example's business domain →
cotwin → solver → reconstructed business domain → independently calculated metrics
flow. It needs OR-Tools and the Python standard library, without GreyJack.

The default `strict` mode requires every facility to stay within capacity and
minimizes setup plus distance cost. Use `--mode penalized` to reproduce the active
source scorer: first minimize total capacity overload, then minimize setup plus
distance cost. The Python API also defaults to `CotwinBuilder(mode="strict")`.

## Run

From the repository root with Python 3.12 or newer:

```bash
python -m pip install -r examples/or_tools/facility_location/requirements.txt
python -m examples.or_tools.facility_location.scripts.solve_task --time-limit 30
```

Direct script execution works from any working directory:

```bash
python /path/to/greyjack-solver-python/examples/or_tools/facility_location/scripts/solve_task.py \
  --mode penalized --workers 1 --time-limit 30
```

The generated demo has 30 facilities and 60 consumers in a rectangular London
area. Seed 0 reproduces the source generator's random sequence without changing
global Python random state. It divides total capacity 4500 equally across
facilities (`150` each) and total demand 900 equally across consumers (`15` each).
The generator uses integer division, just as the source does. No dataset download
is needed.

| Option | Default | Meaning |
| --- | --- | --- |
| `--seed` | `0` | Demo data seed |
| `--mode` | `strict` | `strict` capacity constraints or `penalized` overload scoring |
| `--workers` | `10` | CP-SAT workers |
| `--no-improvement-seconds` | `15` | Stop after this many seconds without an improving incumbent |
| `--time-limit` | None | Optional total search time limit in seconds |
| `--no-greedy-hints` | Off | Disable advisory greedy assignment hints |

The CLI exits with code 0 when it returns an assignment, 1 when the solver returns
no incumbent, and 2 for input or configuration errors. `INFEASIBLE` proves that
no assignment meets strict capacity constraints. `UNKNOWN` may mean a time limit
ended before any incumbent was found. `FEASIBLE` supplies a business assignment
without proving optimality; `OPTIMAL` proves the modeled objective optimum.
Strict mode never falls back to penalized mode.

## Business domain and cotwin

- `domain` holds `Location`, `Facility`, `Consumer`, and `FacilityLocationDomain`.
  Consumer assignment maintains each facility's inverse consumer list.
- `persistence` generates the demo, converts a validated domain to a CP-SAT
  cotwin, and reconstructs assignments by actual business IDs into a copy.
- `cotwin` holds the model and variable mappings. `solver` controls search,
  reports improving incumbents, and returns status and score components.

```python
from examples.or_tools.facility_location.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.facility_location.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.facility_location.solver.FacilityLocationSolver import FacilityLocationSolver

builder = DomainBuilder(seed=0)
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
solution = FacilityLocationSolver(time_limit=30).solve(cotwin)

if solution.has_solution:
    solved_domain = builder.build_from_solution(solution, initial_domain=domain)
    solved_domain.print_metrics()
else:
    print(solution.status, solution.termination_reason)
```

The demo builder API also supports custom totals, counts, setup-cost distribution,
and location bounds. Custom `FacilityLocationDomain` objects may use sparse or
negative integer IDs. Demands and capacities must be nonnegative integers;
setup costs may be signed integers. Coordinates must be finite geographic
latitude/longitude values. A domain with consumers but no facilities is invalid.
An empty domain is supported through `FacilityLocationDomain.empty()`.

## Model and score

Each consumer is assigned to exactly one facility. A facility is used if and
only if at least one consumer is assigned, even when all assigned demands are
zero. For each facility, `load` is total assigned demand and `overload` is
`max(0, load - capacity)`. Distances use the source's planar approximation:

```text
distance_m = ceil(sqrt((latitude difference)^2 +
                       (longitude difference)^2) * 111000)
hard_penalty = sum(facility overload)
soft_cost = 2 * sum(setup cost of used facilities)
          + 5 * sum(consumer-to-facility distance_m)
```

The active source score uses setup coefficient 2 and distance coefficient 5.
Its separate `distance from facility` override field is not read by its active
incremental scorer.

Strict mode adds `load <= capacity` for every facility and minimizes `soft_cost`.
Penalized mode minimizes `W * hard_penalty + soft_cost`, where
`W = upper_bound(soft_cost) - lower_bound(soft_cost) + 1`. This preserves the
source's hard-before-soft ordering, including signed setup costs. Model building
rejects unsafe CP-SAT integer bounds.

The reconstructed domain independently recalculates facility usage, overload,
distance, and setup cost from consumer assignments. It rejects incomplete,
unknown-ID, or score-mismatched solver results and does not alter the input
domain. Each strictly improving `(hard_penalty, soft_cost)` pair is printed and
flushed during search. The no-improvement watchdog can stop a search even if no
new solution callback occurs.

The source's reverse-location lookup was broken and its `Facility.consumers`
member was undefined. This implementation computes distances directly from
business locations and maintains inverse membership with consumer assignments.

Run the package tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/facility_location/tests -v
```
