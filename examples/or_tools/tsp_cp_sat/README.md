# Traveling salesperson with CP-SAT and MTZ

This standalone example reimplements the object-oriented TSP example with
OR-Tools CP-SAT. It follows the business domain -> cotwin -> solver ->
reconstructed business tour -> independent metrics flow. The original GreyJack
example remains available.

## Install and run

From the repository root, with Python 3.12 or newer:

```bash
python -m pip install -r examples/or_tools/tsp_cp_sat/requirements.txt
python -m examples.or_tools.tsp_cp_sat.scripts.solve_tsp
```

The default input is `data/tsp/belgium-n50.tsp`. Pass `--input PATH` for another
TSP file. Direct script execution also works from any working directory. The
CLI accepts `--workers` (default 10), `--no-improvement-seconds` (default 15),
an optional total `--time-limit`, `--no-greedy-hints`, and `--plot`. Plotting
needs matplotlib separately; `--help` works without OR-Tools installed. The
examples environment can run it:

```bash
uv run --project examples --no-sync \
  python -m examples.or_tools.tsp_cp_sat.scripts.solve_tsp
```

## Domain and cotwin

- `domain` holds locations, a vehicle, a route, and the input distance matrix.
  It replays the ordered route and checks exact stop coverage independently of
  the CP-SAT variables.
- `persistence` parses the TSP file, creates the model, and rebuilds a copy of
  the domain from a solution. Original location IDs are preserved; dense indices
  exist only inside the cotwin.
- `cotwin` stores the CP-SAT model, directed arcs, MTZ order variables, and the
  distance objective. `solver` returns status, ordered stop IDs, and distance.

```python
from pathlib import Path

from examples.or_tools.tsp_cp_sat.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.tsp_cp_sat.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.tsp_cp_sat.solver.TSPSolver import TSPSolver

builder = DomainBuilder(Path("data/tsp/belgium-n50.tsp"))
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder().build_cotwin(domain)
solution = TSPSolver(workers=10, no_improvement_seconds=15).solve(cotwin)
if solution.has_solution:
    solved = builder.build_from_solution(solution, initial_domain=domain)
    solved.print_metrics()
```

The first listed location is the depot. Every other location is visited exactly
once, then the tour returns to the depot. Each location has exactly one incoming
and one outgoing selected arc. MTZ order increases along selected arcs between
non-depot locations, so disconnected customer cycles are impossible. Exact
coverage makes the source example's duplicate-stop hard penalty zero.

`EUC_2D` distances match the source solver matrix:
`round(1000 * sqrt((lat1 - lat2)^2 + (lon1 - lon2)^2))`. The reported integer
distance is the objective value; the CLI also divides by 1000 for input units.
`EXPLICIT` requires `EDGE_WEIGHT_FORMAT: FULL_MATRIX`; finite, nonnegative
decimal weights use a common exact power-of-ten scale. The domain replays these
integer matrix weights rather than recomputing raw Euclidean lengths, so its
distance must equal the solver's result. It rejects incomplete tours and score
mismatches.

A nearest-neighbor tour supplies a complete model hint. `OPTIMAL` proves the best
modeled tour; `FEASIBLE` supplies an incumbent without an optimality proof.
The solver prints and flushes each strictly better incumbent distance as it is
found. The idle clock starts immediately before search, resets only on a
strictly better distance, and stops search even if no more callbacks arrive.
An optional total time limit can stop search sooner. A timeout without an
incumbent returns no tour and does not prove infeasibility.
`UNKNOWN`, `INFEASIBLE`, and `MODEL_INVALID` return no tour. The CLI exits 1
when there is no incumbent and 2 for invalid input or options.

The arc model grows quadratically with the number of locations. The CLI accepts
large TSP files but they can require substantial time and memory. It checks
CP-SAT integer bounds before solving.

Run tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/tsp_cp_sat/tests -v
```
