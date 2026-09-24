# Employee scheduling with OR-Tools

This standalone example assigns one employee to each shift using CP-SAT. It
preserves the original employee scheduling flow: business domain -> combinatorial
optimization twin (cotwin) -> solver -> reconstructed business objects -> metrics.
Use Python 3.12 or newer. Its only direct dependency is OR-Tools; the example's
own code otherwise uses the standard library and does not import GreyJack.

Pass `--mode strict` to require zero skill, unavailability, overlap, rest, and
same-day hard penalties, then minimize only preference and fairness cost. The
default `--mode penalized` retains hard/soft scoring. Strict mode returns no
assignment when no valid schedule is found. The Python API uses
`CotwinBuilder(mode="strict")`.

## Install and run

From the repository root:

```bash
python -m pip install -r examples/or_tools/employee_scheduling/requirements.txt
python -m examples.or_tools.employee_scheduling.scripts.solve_task \
  --dataset-size small --seed 45 --start-date 2026-09-28
```

Direct execution also works from any working directory:

```bash
python /path/to/greyjack-solver-python/examples/or_tools/employee_scheduling/scripts/solve_task.py \
  --dataset-size small --start-date 2026-09-28 --workers 1 --time-limit 30
```

If the repository's `examples` environment is already installed, it can also be
used from the repository root:

```bash
uv run --project examples --no-sync \
  python -m examples.or_tools.employee_scheduling.scripts.solve_task \
  --dataset-size small --start-date 2026-09-28
```

The standalone requirements file is sufficient; setting up the broader examples
environment is optional. No dataset download is required. `--help` works without
importing OR-Tools or the business modules.

| Option | Default | Meaning |
| --- | --- | --- |
| `--dataset-size` | `large` | Generated `small` or `large` dataset |
| `--seed` | `45` | Demo-data random seed |
| `--start-date` | Next Monday | First planning date, in `YYYY-MM-DD` format |
| `--workers` | `10` | Positive number of CP-SAT search workers |
| `--no-improvement-seconds` | `15` | Stop after this long without a strictly better score |
| `--time-limit` | None | Optional positive total search time limit, in seconds |
| `--mode` | `penalized` | Use `strict` for hard scheduling requirements and a soft-only objective |

The default planning date is the first Monday on or after today, resolved once
when `DomainBuilder` is constructed. An explicit date is used as given, including
non-Mondays. Specify both seed and date to reproduce the generated business data.
Seed 45 produces 15 employees and 138 shifts over 14 days for `small`, or 50
employees and 914 shifts over 28 days for `large`. Seed 37 reproduces the original
generator's random sequence: 139 and 935 shifts respectively. These counts are
checks of those seeds, not constraints on other generated instances.

## Domain and cotwin APIs

- `domain`: `Employee`, `Shift`, and `EmployeeSchedule` hold business data and
  independently calculate all score components without importing OR-Tools.
- `persistence`: `DomainBuilder` generates data and reconstructs solutions;
  `CotwinBuilder` converts the validated domain to a CP-SAT model.
- `cotwin`: `CotEmployeeSchedule` owns the model, assignment variables, component
  penalties, workload counts, and hard/soft totals.
- `solver`: `EmployeeSchedulingSolver` returns `EmployeeSchedulingSolution`;
  `ScoreNoImprovement` reports improving incumbents and controls idle stopping.
- `scripts`: `solve_task.py` connects these stages and prints the result.

```python
from datetime import date

from examples.or_tools.employee_scheduling.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.employee_scheduling.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.employee_scheduling.solver.EmployeeSchedulingSolver import EmployeeSchedulingSolver

builder = DomainBuilder(
    random_seed=45, dataset_size="small", start_date=date(2026, 9, 28)
)
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder().build_cotwin(domain)
solution = EmployeeSchedulingSolver(
    workers=10, no_improvement_seconds=15, time_limit=30
).solve(cotwin)

if solution.has_solution:
    solved_domain = builder.build_from_solution(solution, initial_domain=domain)
    solved_domain.print_schedule()
    solved_domain.print_metrics()
else:
    print(solution.status, solution.termination_reason)
```

`solution.assignments` maps actual integer `Shift.id` values to employee **list
indices**. Shift IDs can be sparse, negative, or reordered. Reconstruction copies
the initial domain, applies assignments by ID, and checks independently
recalculated hard and soft totals against the solver result. Existing assignments
are advisory hints and remain editable. Reconstruction never changes the original
domain. If `initial_domain` is omitted, the same builder regenerates its dataset.

Custom domains must have unique integer shift IDs, valid employee indices, date-only
availability/preferences, and naive, minute-aligned start/end datetimes with
`end > start`. Both empty schedules and employees without shifts are supported;
shifts without employees are rejected. Model construction rejects unsafe CP-SAT
integer bounds.

## Exact hard/soft scoring

Every shift has exactly one employee. Business violations are penalized, so a
returned assignment can still have missing skills or scheduling conflicts.
The solver first minimizes the hard penalty, then the soft penalty.

Each assigned shift contributes these hard penalties:

- Missing required skill: `+1`.
- Employee unavailable on the shift's **start date**: `+1`.

For each unordered pair of shifts assigned to the same employee:

- If they overlap, add **twice** the overlap duration in minutes.
- Otherwise, add **twice** the rest shortage below 600 minutes. Touching shifts
  have zero rest and contribute 1,200.
- Independently, add `+2` if both shifts start on the same date.

The factors of two preserve the source scorer's evaluation of both pair orders.
Overlap and rest are alternatives for a pair; the same-start-date penalty can
apply alongside either. Overnight shifts use their real end datetime, while
availability and preferences use only the start date.

The unrounded soft penalty is the number of assignments on undesired dates minus
the number on desired dates, plus workload unfairness:

```text
N = number of shifts
M = number of employees
c[e] = assigned shift count for employee e, including employees with zero shifts
P = undesired-date assignments - desired-date assignments
unfairness = sqrt(sum((c[e] - N/M)^2))
Q = M * sum(c[e]^2) - N^2
F = floor(100 * sqrt(Q/M))
soft_penalty_cents = 100 * P + F
```

Because `P` is an integer, this is exactly the total soft penalty floored to two
decimal places, including negative scores. Integer arithmetic avoids rounding
errors at the two-decimal boundary. The CP-SAT model enforces
`M * F^2 <= 10000 * Q < M * (F + 1)^2`, making fairness exact for every assignment.
For an empty schedule with no employees, workload unfairness and both scores are
defined as zero.

Let `Fmax = floor(100 * sqrt(N^2 * (M - 1) / M))` for `M > 0`, otherwise zero.
The scalar objective is:

```text
W = 200 * N + Fmax + 1
objective = W * hard_penalty + soft_penalty_cents
```

The soft score lies between `-100*N` and `100*N + Fmax`, so reducing the hard
penalty by one always dominates any possible soft-score change.

## Search output and termination

Each strictly improving integer `(hard_penalty, soft_penalty_cents)` pair is
printed and flushed immediately, for example:

```text
[1.234s] New best solution #1: hard_penalty=4, soft_penalty_cents=652
[2.345s] New best solution #2: hard_penalty=2, soft_penalty_cents=781
```

These lines are illustrative. Equal or worse scores neither print nor reset the
idle timer. The timer starts immediately before solving and a watchdog stops the
search even if no solution callback occurs. Cleanup joins the watchdog whether
search succeeds or raises. Model construction and validation happen before the
search timers. CP-SAT presolve is disabled: probing the dense default dataset can
consume the entire 15-second idle window before any incumbent is returned. In a
controlled large-dataset check, disabling presolve allowed the first incumbent
after about 10 seconds and a zero-hard-penalty assignment after about 13 seconds;
these timings are machine- and workload-dependent. Termination is cooperative,
so solver return can occur slightly after a configured deadline.
The solver seed is fixed at zero; parallel search and wall-clock limits can still
produce different incumbents across runs.

After search, the CLI prints status, termination reason, elapsed search time,
every reconstructed shift assignment, workload per employee, mean workload,
each hard/soft component, and `Business feasible`. `OPTIMAL` proves the best
modeled hard/soft score; `FEASIBLE` returns an incumbent without that proof.
Either can contain business violations. Business feasibility requires a zero
hard penalty.

`UNKNOWN`, `INFEASIBLE`, and `MODEL_INVALID` supply no assignment or score values.
A short limit can expire during solver initialization and return `UNKNOWN`. The CLI exits with
code 0 when an assignment is returned, including one with violations; code 1
when no assignment is returned; and code 2 for invalid input or configuration.

## Differences from the original example

The original cotwin builder previously copied shift starts into both the
shift-end and shift-start-date arrays. Both examples now use actual ends and
calendar dates for overlap, rest, availability, and preference semantics.
It retains the source's twice-counted pair rules and floors the complete soft
score to two decimal places instead of optimizing the unrounded square root.

The original domain builder accepts seed 45 but its generator uses seed 37.
This example honors the requested seed, keeps generator state local, and fixes
the planning date for the builder's lifetime. The original example's generator
still retains its previous seed behavior.

Run the standard-library test suite from the repository root:

```bash
python -m unittest discover -s examples/or_tools/employee_scheduling/tests -v
```

The tests cover independent score enumeration, individual constraint components,
hard/soft priority, reconstruction, reproducible generation, CLI behavior,
configuration errors, and watchdog cleanup.
