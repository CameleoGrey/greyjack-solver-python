# Cloud balancing with Lagrangian relaxation

This standalone example retains the original cloud-balancing JSON schema and
business score. Its flow is **domain → cotwin → solver → reconstructed domain →
independent metrics**. It does not import GreyJack or the sibling CP-SAT example.
Use Python 3.12 or newer and OR-Tools 9.15 or newer.

## Run

From the repository root:

```bash
python -m pip install -r examples/or_tools/cloud_balancing_lagrangian/requirements.txt
python -m examples.or_tools.cloud_balancing_lagrangian.scripts.solve_cloud_balancing \
  --time-limit 30
```

The direct script path also works from another working directory. By default it
reads `data/cloudbalancing/400computers-1200processes.json`. Select another
dataset with `--input`. The input is never modified.

| Option | Default | Meaning |
| --- | --- | --- |
| `--input` | Native 400/1200 JSON | Cloud-balancing dataset |
| `--mode` | `strict` | Require capacity or penalize overload |
| `--no-improvement-seconds` | `120` | Stop after this long without a better complete score |
| `--time-limit` | None | Optional total wall-time limit |
| `--max-iterations` | None | Optional dual-iteration limit |
| `--no-greedy-seed` | Off | Skip the initial first-fit assignment |

The Python builder defaults to `penalized`, as in the source example; the CLI
defaults to `strict`. The CLI exits 0 with a complete assignment, 1 without one,
and 2 for invalid input or settings.

## Business model and relaxation

Each process is assigned to one computer. A computer incurs its cost once if it
hosts any process. The three resources are CPU, memory, and network bandwidth.
`strict` requires every load to fit. `penalized` measures each overload as
`max(0, load - capacity)` and minimizes `(hard_penalty, soft_cost)` in that order.
The equivalent integer objective uses `W = sum(computer costs) + 1`:

```text
minimize W * sum(overload[c,r]) + sum(cost[c] * used[c])
subject to sum_c assigned[p,c] = 1                 for each process p
           sum_p demand[p,r] * assigned[p,c]
               <= capacity[c,r] + overload[c,r]   for each computer c, resource r
           sum_p assigned[p,c] <= P * used[c]      for each computer c
```

Strict mode has zero overload and minimizes only used-computer cost. The solver
relaxes the capacity and aggregate activation links with nonnegative multipliers
`mu[c,r]` and `lambda[c]`. In penalized mode, `mu[c,r] <= W`. For fixed prices,
the remaining OR-Tools GLOP model has independent process-assignment groups and
computer-activation choices. Processes with the same demand vector share one
group with integer multiplicity; the group's simplex has an integral optimum.
The dual value is:

```text
- sum(mu[c,r] * capacity[c,r])
+ sum_p min_c(lambda[c] + sum_r(mu[c,r] * demand[p,r]))
+ sum_c min(0, cost[c] - P * lambda[c])
```

Projected subgradient steps update the prices. Tied minimum-cost assignments
are shared when calculating an ascent direction, and a bounded step search
avoids large moves that lower the dual value. The best dual value is recomputed
with exact decimal arithmetic before reporting it. A first-fit seed and a
dual-guided, capacity-aware greedy assignment provide primal candidates; a
single relocation pass seeks a better business score. Every accepted candidate
is checked by the independent domain metrics before it is logged or returned.

`New best solution` lines are flushed immediately and appear only for strictly
better complete `(hard_penalty, soft_cost)` scores. The idle timer starts at
solve entry and resets only for those improvements. Dual-bound improvement does
not reset it. Limits are checked between search stages, so a long repair can
finish slightly after a deadline. `FEASIBLE` means a checked assignment exists
without an optimality proof. `OPTIMAL` requires the certified lower bound to
close the integer gap.
`INFEASIBLE` is used only for a direct necessary-condition proof; an unsuccessful
strict repair otherwise returns `UNKNOWN`. An idle, time, or iteration limit is
reported separately from status.

The business classes, JSON loading, and reconstruction follow the original
example. IDs need not be contiguous. Input assignments are editable, not fixed.
Reconstruction deep-copies the domain, applies IDs, and rejects incomplete or
score-inconsistent results. Zero-demand processes still activate computers.

Run focused checks from the repository root:

```bash
python -m unittest discover -s examples/or_tools/cloud_balancing_lagrangian/tests -v
```
