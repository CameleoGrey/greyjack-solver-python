# Cloud balancing with OR-Tools

This standalone version preserves the object-oriented example's business domain,
combinatorial optimization twin (cotwin), conversion back to business objects,
and resource metrics. Its runtime dependencies are OR-Tools and the Python
standard library; installing GreyJack is unnecessary.

Pass `--mode strict` to enforce each computer's CPU, memory, and network
capacity and minimize only used-computer cost. The default `--mode penalized`
retains overload-first scoring. Strict mode returns no assignment when no
capacity-feasible incumbent is found; a timeout is distinct from proven
infeasibility. The Python API uses `CotwinBuilder(mode="strict")`.

## Install and run

Use Python 3.9 or newer. From the repository root:

```bash
python -m pip install -r examples/or_tools/cloud_balancing/requirements.txt
python -m examples.or_tools.cloud_balancing.scripts.solve_cloud_balancing \
  --input /path/to/400computers-1200processes.json
```

Direct execution also works, including from another working directory:

```bash
python /path/to/greyjack-solver-python/examples/or_tools/cloud_balancing/scripts/solve_cloud_balancing.py \
  --input /path/to/4computers-12processes.json --workers 1 --time-limit 60
```

Without `--input`, the script looks for
`data/cloudbalancing/400computers-1200processes.json` relative to the repository
root. Datasets are separate from this repository; use an existing dataset or get
them from [GreyJack example data](https://github.com/CameleoGrey/greyjack-data-for-examples).
The script reads the input without modifying it.

| Option | Default | Meaning |
| --- | --- | --- |
| `--input` | Dataset path above | Cloud-balancing JSON file |
| `--workers` | `8` | CP-SAT search workers |
| `--no-improvement-seconds` | `120` | Stop after this long without a strictly better score |
| `--time-limit` | None | Optional total search time limit, in seconds |
| `--no-greedy-hints` | Off | Disable the first-fit initialization hints |
| `--mode` | `penalized` | Use `strict` for hard resource capacities and a cost-only objective |

The idle timer starts when search starts and resets on each improving incumbent.
A watchdog stops idle searches even when there are no solution callbacks. Model
construction and validation precede the search timers. Termination is cooperative,
so returning from the native solver can take slightly longer than a time limit.
CP-SAT model presolve is disabled: on the default dense dataset it can consume the
idle window before returning a known feasible first-fit hint. The hint remains
advisory, and CP-SAT continues searching for improvements.

## Domain and cotwin flow

The layout follows the original example, with one class per file:

- `domain`: `Computer`, `Process`, and `ScheduleCB` hold business data and calculate
  metrics without importing OR-Tools.
- `persistence`: `DomainBuilder` loads JSON and reconstructs solved domains;
  `CotwinBuilder` converts a domain into the mathematical model.
- `cotwin`: `CotScheduleCB` owns the CP-SAT model, variables, and business ID mappings.
- `solver`: `CloudBalancingSolver` manages search and returns a
  `CloudBalancingSolution`; `ScoreNoImprovement` manages the idle cutoff.
- `scripts`: the command-line example connects these stages.

```python
from pathlib import Path

from examples.or_tools.cloud_balancing.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.cloud_balancing.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.cloud_balancing.solver.CloudBalancingSolver import CloudBalancingSolver

domain_builder = DomainBuilder(Path("/path/to/cloud-balancing.json"))
domain = domain_builder.build_domain_from_scratch()
cotwin = CotwinBuilder(use_greed_init=True).build_cotwin(domain)
solution = CloudBalancingSolver(workers=10, no_improvement_seconds=15).solve(cotwin)

if solution.has_solution:
    solved_domain = domain_builder.build_from_solution(solution, initial_domain=domain)
    solved_domain.print_metrics()
else:
    print(solution.status, solution.termination_reason)
```

Reconstruction copies the original domain, assigns computers by their actual IDs,
and checks the independently recalculated domain scores against the solver result.
IDs need not be contiguous or match list positions. Existing assignments remain
editable. First-fit hints follow process/computer input order and are advisory;
processes that do not fit during initialization remain unhinted.

## Input and objective

The JSON schema matches the original example:

```json
{
  "computerList": [
    {"id": 41, "cpuPower": 8, "memory": 16, "networkBandwidth": 4, "cost": 100}
  ],
  "processList": [
    {"id": 83, "requiredCpuPower": 2, "requiredMemory": 4, "requiredNetworkBandwidth": 1, "computer": null}
  ],
  "score": null
}
```

Resource capacities, demands, and costs must be nonnegative integers. IDs must be
integers, unique within each list; `computer` must be null or a known computer ID.
The input `score` is ignored. Empty process lists are supported. Processes without
any computers, invalid fields, and unsafe CP-SAT integer bounds produce errors.

Each process is assigned to exactly one computer. For every computer and each of
CPU, memory, and network bandwidth, the model calculates:

```text
overload = max(0, total assigned demand - capacity)
hard_penalty = sum of all overloads
soft_cost = sum of costs of computers hosting at least one process
objective = hard_penalty * (sum of all computer costs + 1) + soft_cost
```

Both score components are minimized. The weight guarantees that reducing overload
by one unit is always preferable to any cost saving, matching the original
hard/soft ordering. Cost is charged once per used computer, including when its
processes have zero resource demands.

## Results and checks

During search, each strictly better solution is printed immediately to stdout,
with its sequence number, elapsed search time, hard penalty, and soft cost:

```text
[1.850s] New best solution #1: hard_penalty=0, soft_cost=120882
[4.210s] New best solution #2: hard_penalty=0, soft_cost=120452
```

Output is flushed for every improvement, including when stdout is redirected.
Equal or worse scores are omitted, using the same hard/soft ordering as the
no-improvement timer.

The CLI prints solver status, termination reason, elapsed search time, resource
usage and process IDs per used computer, violation count, computers used, total
overload, total cost, and resource feasibility. A violation counts one overloaded
resource on one computer; the hard penalty measures the amount of overload.

`OPTIMAL` proves the best hard/soft score. `FEASIBLE` supplies an assignment without
an optimality proof. Either status may contain resource overload, because the
model minimizes overload rather than forbidding it. Consult `Resource feasible`
and the hard penalty to assess the business assignment.

`UNKNOWN` means search stopped without returning an incumbent, which can happen
if a limit expires during initialization. `INFEASIBLE` and `MODEL_INVALID` also
produce no assignments. The CLI exits with code 0 when it returns an assignment
(including an overloaded one), 1 when search returns no assignment, and 2 for an
input/configuration error. The solution object never supplies variable values
for a status without an assignment.

Run the standard-library test suite from the repository root:

```bash
python -m unittest discover -s examples/or_tools/cloud_balancing/tests -v
```

Tests compare small instances against exhaustive enumeration and check ID-based
reconstruction, all resource penalties, activation costs, input validation,
greedy hints, command-line execution, and watchdog cleanup.
