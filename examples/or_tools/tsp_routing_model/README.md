# Traveling salesperson with OR-Tools RoutingModel

This standalone example solves the object-oriented TSP through a business
domain, a RoutingModel cotwin, and an independently reconstructed tour. It does
not import GreyJack or the sibling CP-SAT example.

## Run

From the repository root, with Python 3.12 or newer:

```bash
python -m pip install -r examples/or_tools/tsp_routing_model/requirements.txt
python -m examples.or_tools.tsp_routing_model.scripts.solve_tsp
```

The default is `data/tsp/pcb442.tsp`. Use `--input PATH` for another TSP file.
The script lists every checked-in TSP dataset as a selectable default.
`--no-improvement-seconds` defaults to 15. `--time-limit` optionally caps total
search time; no total cap is set by default. `--plot` shows a matplotlib tour.
Direct script execution works from any working directory, and `--help` works
before OR-Tools is installed. The examples environment can also run it:

```bash
uv run --project examples --no-sync \
  python -m examples.or_tools.tsp_routing_model.scripts.solve_tsp \
  --time-limit 10
```

## Domain, cotwin, and score

`DomainBuilder` reads the input and builds business `Location`, `Vehicle`, and
`TravelSchedule` objects. The first listed location is the depot. All others
are mandatory stops and must occur once before returning to the depot. Actual
location IDs stay in the domain and solution; the cotwin uses dense RoutingModel
indices. `DomainBuilder.build_from_solution()` reconstructs a copy of the
business schedule, independently replays its tour, and rejects missing or
repeated stops or a distance mismatch.

`EUC_2D` distances match the source solver's
`round(1000 * sqrt((lat1 - lat2)^2 + (lon1 - lon2)^2))` matrix. `EXPLICIT`
requires `EDGE_WEIGHT_FORMAT: FULL_MATRIX`; finite, nonnegative decimal weights
are scaled exactly to integers. The objective and replay use those integer
matrix units. The CLI also prints distance in input units. The original
duplicate-stop hard penalty is zero because RoutingModel visits each mandatory
stop once.

RoutingModel starts with `PATH_CHEAPEST_ARC` and improves with
`GUIDED_LOCAL_SEARCH`. The CLI prints and flushes each strictly better distance.
Its idle search limit starts before solving and resets only on improvement; it
can also stop search before the first tour. If no incumbent is returned, the CLI
exits 1 without reconstructing a route; malformed input or options exit 2.
`ROUTING_FAIL` or a timeout is not proof of infeasibility. A returned heuristic
tour is not an optimality proof unless its status is `ROUTING_OPTIMAL`.

The input parser builds a full distance matrix and memory use grows with the
square of the location count. It rejects unsafe RoutingModel integer bounds.

```python
from pathlib import Path

from examples.or_tools.tsp_routing_model.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.tsp_routing_model.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.tsp_routing_model.solver.TSPSolver import TSPSolver

builder = DomainBuilder(Path("data/tsp/pcb442.tsp"))
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder().build_cotwin(domain)
solution = TSPSolver(no_improvement_seconds=15).solve(cotwin)
if solution.has_solution:
    solved = builder.build_from_solution(solution, initial_domain=domain)
    solved.print_metrics()
```

Run tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/tsp_routing_model/tests -v
```
