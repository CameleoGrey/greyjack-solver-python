# Vehicle routing with OR-Tools RoutingModel

This standalone example solves the object-oriented VRP through business domain
objects, a RoutingModel cotwin, and independently reconstructed business routes.
It does not import GreyJack or the sibling CP-SAT example.

Pass `--mode strict` to enforce vehicle capacities, customer service-completion
windows, and vehicle workday ends, then minimize only route distance. The
default `--mode penalized` retains overload/lateness/distance scoring. Both
modes require every customer exactly once and use the existing service-only
clock. Strict mode returns no routes if no feasible incumbent is found; a
timeout is not proof of infeasibility. The Python API uses
`CotwinBuilder(mode="strict")`.
`ROUTING_FAIL` reports that no route was found; only `ROUTING_INFEASIBLE`
reports proven infeasibility.

## Run

From the repository root, with Python 3.12 or newer:

```bash
python -m pip install -r examples/or_tools/vrp_routing_model/requirements.txt
python -m examples.or_tools.vrp_routing_model.scripts.solve_vrp
```

The default input is the checked-in 500-location, five-depot Belgium dataset.
Use `--input PATH` for another VRP file, such as the 50-location dataset for a
quick run. Searches stop after 15 seconds without an improvement or 6,000
seconds in total; change these with
`--no-improvement-seconds` and `--time-limit`. `--plot` adds an optional
matplotlib route plot. The CLI prints each strictly improving score tuple and
then prints independently replayed business metrics and routes. RoutingModel
search is heuristic; a returned route is not an optimality proof unless its
status says `ROUTING_OPTIMAL`.

The broader examples environment can also run this package:

```bash
uv run --project examples --no-sync \
  python -m examples.or_tools.vrp_routing_model.scripts.solve_vrp \
  --time-limit 10
```

## Domain and score

`DomainBuilder` reads locations, customer demands, depots, vehicles, and a
distance matrix. `CotwinBuilder` maps their IDs to RoutingModel nodes and
vehicle-specific depot starts and ends. Every non-depot customer is mandatory
and visited exactly once; empty vehicles are allowed. `VRPSolver` returns
ordered customer IDs. `DomainBuilder.build_from_solution()` rebuilds a copy of
the domain, checks coverage, and independently recalculates the score.

The objective matches the active object-oriented scorer in lexicographic order:

1. Sum of vehicle capacity overloads.
2. Sum of customer service completion beyond its window end and used-vehicle
   completion beyond its workday end.
3. Total route distance, including depot departure and return arcs.

Capacity and time violations are penalized, so the solver can still return all
customers when zero-penalty routes are impossible. The time clock starts at the
vehicle workday start, waits for early customer windows, and advances by service
time. Travel distance does **not** advance this clock, matching the source
scorer. The cotwin divides all clock values by their greatest common divisor
when possible, then restores seconds in the result. Integer weights preserve
the score order; unsafe integer bounds are rejected before search. OR-Tools
routing dimensions supply the cumulative load and time values and their soft
upper-bound costs.

## Input formats

Both formats require `NAME` ending in `-k<vehicle count>`, `DIMENSION`,
`CAPACITY`, `NODE_COORD_SECTION`, `DEMAND_SECTION`, and `DEPOT_SECTION`. Each
coordinate row is `id latitude longitude [name]`. Demand rows are either
`id demand` or `id demand window_start window_end service_time`, consistently
for every location. Depot IDs terminate with `-1`.

- `EDGE_WEIGHT_TYPE: EUC_2D` computes integer distances by rounding 1,000
  times Euclidean coordinate distance, as in the checked-in datasets.
- `EDGE_WEIGHT_TYPE: EXPLICIT` requires `EDGE_WEIGHT_FORMAT: FULL_MATRIX` and
  `EDGE_WEIGHT_SECTION`. It contains exactly `DIMENSION × DIMENSION`
  nonnegative integer values in `NODE_COORD_SECTION` order. Rows may wrap;
  asymmetric distances are supported.

For example, the explicit matrix section for three locations is:

```text
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: FULL_MATRIX
EDGE_WEIGHT_SECTION
0 7 2
6 0 5
3 4 0
```

Run the standalone tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/vrp_routing_model/tests -v
```
