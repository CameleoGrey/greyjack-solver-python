# Vehicle routing with CP-SAT

This standalone example solves the object-oriented VRP example with OR-Tools
CP-SAT. It keeps the business domain -> cotwin -> solver -> reconstructed
business routes -> independent metrics flow. The original GreyJack example and
the standalone OR-Tools `RoutingModel` example remain available.

The CLI defaults to `--mode strict`, which enforces vehicle capacities,
customer service-completion windows, and vehicle workday ends, then minimizes
route distance. `--mode penalized` retains overload/lateness/distance scoring.
The Python API defaults to `CotwinBuilder(mode="penalized")`; pass
`mode="strict"` for the CLI behavior. Both modes require every customer exactly
once and use the existing service-only clock. Strict mode returns no routes if
no feasible incumbent is found; a timeout is not proof of infeasibility.

## Install and run

From the repository root, with Python 3.12 or newer:

```bash
python -m pip install -r examples/or_tools/vrp_cp_sat/requirements.txt
python -m examples.or_tools.vrp_cp_sat.scripts.solve_vrp
```

The checked-in `data/vehiclerouting/belgium-tw-d2-n50-k10.vrp` dataset is the
default. Use `--input PATH` for another file in the same `EUC_2D` VRP format.
Direct script execution works from any working directory. The broader examples
environment can also run it:

```bash
uv run --project examples --no-sync \
  python -m examples.or_tools.vrp_cp_sat.scripts.solve_vrp \
  --workers 1 --time-limit 60
```

Options are `--workers` (default 10), `--no-improvement-seconds` (default 180),
`--time-limit` (optional total solver limit), `--no-greedy-hints`, `--plot`,
`--mode {penalized,strict}` (CLI default `strict`), and
`--formulation {mtz,circuit}` (default `mtz`). To compare formulations on the
same input, run once with `--formulation mtz` and once with
`--formulation circuit`, keeping the other options fixed.
Plotting needs matplotlib installed separately. `--help` works before installing
OR-Tools. The parser accepts the checked-in `NODE_COORD_SECTION`,
`DEMAND_SECTION`, and `DEPOT_SECTION` layout. It rejects unsupported edge-weight
formats and malformed data.

## Domain and cotwin

- `domain` contains `Customer`, `Vehicle`, and `VehicleRoutingPlan`. It calculates
  route metrics from customer IDs and the input distance matrix without OR-Tools.
- `persistence` reads the VRP file, constructs the CP-SAT cotwin, and rebuilds a
  copy of the business domain from solver routes.
- `cotwin` stores the CP-SAT model, arcs, score components, and location
  mappings. Its order-variable map is empty in circuit mode.
- `solver` reports status, ordered routes, and score components. A callback
  prints and flushes each strictly improving `(hard, medium, distance)` tuple.

```python
from pathlib import Path

from examples.or_tools.vrp_cp_sat.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.vrp_cp_sat.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.vrp_cp_sat.solver.VRPSolver import VRPSolver

builder = DomainBuilder(Path("data/vehiclerouting/belgium-tw-d2-n50-k10.vrp"))
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder(formulation="circuit").build_cotwin(domain)
solution = VRPSolver(workers=10, no_improvement_seconds=15).solve(cotwin)
if solution.has_solution:
    solved = builder.build_from_solution(solution, initial_domain=domain)
    solved.print_metrics()
```

Every delivery customer appears exactly once. A vehicle uses one route from its
own depot back to the same depot, or remains unused. The default MTZ formulation
increases a shared order variable on selected customer-to-customer arcs. The
alternative `add_circuit()` formulation uses one circuit per vehicle, with
self-loops for unused vehicles and customers assigned to other vehicles. Both
exclude disconnected subtours. Actual customer IDs are retained in the domain
and result; dense indices stay inside the cotwin. The reconstruction
independently replays the routes and checks all three score components against
the solver. It never modifies the input domain.

## Score semantics

The active source VRP scorer ranks solutions lexicographically:

1. **Hard:** sum of `max(0, vehicle demand - vehicle capacity)`.
2. **Medium:** sum of customer completion time beyond its time-window end, plus
   each used vehicle's completion time beyond its workday end.
3. **Soft:** total route distance, including departure and return arcs.

The original search also penalizes duplicate customer selections; exact coverage
makes that penalty zero in this model. Capacity and time penalties can remain
positive in a returned solution. `OPTIMAL` proves the best modeled score;
`FEASIBLE` gives an incumbent without an optimality proof. A result is business
feasible only when both hard and medium penalties are zero.

To match the active scorer, a vehicle clock starts at its depot workday start.
At each customer it waits until the window start if early, then adds service
duration. Travel distance does **not** advance this clock. Customer lateness is
`max(0, service completion - window end)`. For datasets without time windows,
the medium score is zero. All score values are integers; bounded weights make
the CP-SAT scalar objective preserve hard/medium/soft ordering exactly.

The builder supplies a complete deterministic initial route hint. It fills
vehicles with nearest customers while capacity permits, then assigns remaining
customers to the least additionally overloaded vehicle. The hint is advisory.
The 15-second idle timer starts immediately before solving and resets on a
strictly better score. A watchdog also stops searches that produce no callback.
`UNKNOWN`, `INFEASIBLE`, and `MODEL_INVALID` carry no routes; the CLI exits with
code 1 when no incumbent is returned and code 2 for invalid input or options.

Both formulations create customer-pair arc variables for each vehicle, so model
size grows roughly with vehicles times customers squared. Circuit mode omits MTZ
order variables and arc-conditioned order constraints; neither formulation is
guaranteed to solve faster. The default 50-location dataset is a practical
quick-run choice; the 500-location dataset may require substantial time and
memory. Unsafe CP-SAT integer bounds are rejected before search.

Run the standalone tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/vrp_cp_sat/tests -v
```
