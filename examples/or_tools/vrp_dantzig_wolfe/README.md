# Vehicle routing with Dantzig–Wolfe decomposition

This standalone OR-Tools example solves the same business VRP as
`vrp_cp_sat`. It follows domain → cotwin → route pricing → master → reconstructed
business routes → independent metrics. The solver core imports no code from
sibling examples; the benchmark runner invokes them as baselines.

## Run

From the repository root with Python 3.12 or newer:

```bash
python -m pip install -r examples/or_tools/vrp_dantzig_wolfe/requirements.txt
python -m examples.or_tools.vrp_dantzig_wolfe.scripts.solve_vrp
```

The default is the checked-in 50-location Belgium dataset, strict mode, fast
pricing, and a 30-second total limit. `--input PATH` selects another `EUC_2D` VRP file in the
same format. `--mode penalized` uses lexicographic overload, time penalty, then
distance; strict mode enforces zero overload and zero time penalty, then minimizes
distance. `--pricing exact` requests convergence-capable SCIP pricing;
`--seed-time-limit` and `--workers` apply to a CP-SAT fallback if native route
generation finds no strict incumbent. `--no-seed` disables the initial route
pool. `--plot` requires matplotlib separately.
`--help` works before OR-Tools is installed.

The Python API uses `CotwinBuilder(mode="penalized")` by default:

```python
from pathlib import Path

from examples.or_tools.vrp_dantzig_wolfe.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.vrp_dantzig_wolfe.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.vrp_dantzig_wolfe.solver.VRPSolver import VRPSolver

builder = DomainBuilder(Path("data/vehiclerouting/belgium-tw-d2-n50-k10.vrp"))
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
result = VRPSolver(time_limit=30, pricing_mode="fast").solve(cotwin)
if result.has_solution:
    solved = builder.build_from_solution(result, initial_domain=domain)
    solved.print_metrics()
```

## Model and status

One column is an ordered nonempty route from a vehicle's depot back to the same
depot. Identical vehicles are grouped by depot, capacity, and workday. The
restricted master covers every customer exactly once and uses at most the
available vehicles in each group; unused vehicles have no column. Two native
RoutingModel searches collect routes from complete solutions, then the SCIP
integer master recombines them. GLOP duals guide a fast one-vehicle RoutingModel
pricer. Its scaled objective proposes routes; the cotwin recomputes every
reduced cost before adding a column. In `exact` mode, SCIP pricing verifies that
no improving route remains when the fast pricer stalls. Artificial columns
establish initial LP feasibility when no complete seed is available.

The business clock starts at the vehicle depot start, waits for a customer
window, and advances by service duration. Travel distance does not advance
time. Hard score is total capacity overload. Medium score is customer service
completion lateness plus used-vehicle workday lateness. Soft score is total
route distance including depot departure and return. Actual location IDs are
retained; route columns are independently replayed through copied business
domain objects before a result is returned.

`FEASIBLE` means a complete, independently validated integer route assignment.
`INFEASIBLE` is reserved for a CP-SAT seed proof or a converged phase-one LP
proof. `UNKNOWN` means no integer assignment was found within the limit.
`restricted_master_status=OPTIMAL` proves only the best combination of generated
columns. Fast mode never sets `lp_converged=True`. Exact mode sets it only when
all root LP pricing subproblems prove that no improving route remains; it does
not prove global integer optimality. A timeout can still return the best
validated complete assignment. The CLI shows generator, pool-master, and final
scores separately, together with stage timings.

During solving, each strictly better complete assignment prints and flushes a
line such as `[1.234s] New best solution #2: hard_penalty=0,
medium_penalty=0, distance=15982`. The counter and elapsed clock span the
greedy seed, both route-pool searches, the CP-SAT fallback, and integer-master
solves. LP column messages are separate; they do not represent complete routes.

## Performance boundary

The fast default targets the checked-in 50- and 100-location files. It spends
up to 10 seconds on each of two complete-route searches, then uses the
remaining budget for dual-guided pricing and reserves two seconds for the final
master. It does not split customers into independent regions or provide a
large-instance speed guarantee. Exact SCIP pricing still considers every
customer in each vehicle group and may be slow.

Benchmark strict mode against both sibling examples with three serial runs per
dataset and an end-to-end 30-second wall-clock budget:

```bash
python -m examples.or_tools.vrp_dantzig_wolfe.scripts.benchmark_vrp \
  --time-limit 30 --repeats 3 --output /tmp/vrp_dw_benchmark.json
```

The report includes independently replayed scores, wall time, CPU time, and
the generator and master contributions. Penalized mode is correctness-tested
but has no performance target.

Run tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/vrp_dantzig_wolfe/tests -v
```
