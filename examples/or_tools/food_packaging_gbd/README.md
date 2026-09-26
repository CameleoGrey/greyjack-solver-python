# Food packaging with Generalized Benders decomposition

This standalone OR-Tools example retains the source business domain → cotwin →
solver → reconstructed domain → independent metrics flow. It copies the same
generator and score rules as `food_packaging`; it does not import that package
or GreyJack. Python 3.12 or newer and OR-Tools 9.15 or newer are required.

## Run

From the repository root:

```bash
python -m pip install -r examples/or_tools/food_packaging_gbd/requirements.txt
python -m examples.or_tools.food_packaging_gbd.scripts.solve_task \
  --time-limit 30 --no-schedule
```

Direct execution of `scripts/solve_task.py` also works. The native default
generates 60 products, five lines, and 100 jobs. Fix `--seed` and `--start-date`
to compare runs. The CLI defaults to `--mode penalized`, matching the source
script (whose README says `strict`). The Python `CotwinBuilder` defaults to
`strict`, also matching the source API.

| Option | Default | Meaning |
| --- | --- | --- |
| `--line-count` | `5` | Generated lines |
| `--job-count` | `100` | Generated jobs |
| `--seed` | `37` | Generator seed |
| `--start-date` | Next Monday | Planning start date, `YYYY-MM-DD` |
| `--mode` | `penalized` | `strict` or `penalized` scoring |
| `--workers` | `10` | CP-SAT workers for master and integer timing |
| `--no-improvement-seconds` | `180` | Wall seconds without a better complete score |
| `--time-limit` | None | Optional total wall seconds |
| `--no-greedy-hints` | Off | Skip the deterministic initial seed |
| `--no-schedule` | Off | Suppress per-job schedule output |

## Business score and decomposition

Every job belongs to one line in an ordered route. Its start must follow the
line start or the prior job's end plus *incoming* product cleaning time. The
score is `(hard, medium, soft)` in lexicographic order:

```text
hard   = sum(max(0, job_end - latest_end))
medium = sum((last_job_end - line_start)^2) over nonempty lines
soft   = pairwise same-operator production overlap
       + sum(max(0, job_end - ideal_end))
       + sum(incoming_job.priority * preceding_cleaning)
```

Strict mode requires zero hard lateness, no early starts, and no shared-operator
production overlap. Penalized mode does not enforce minimum starts or operator
nonoverlap. Both modes require complete, exactly-once job coverage. Cleaning
delays the next job on its line but does not reserve an operator.

The CP-SAT master selects line routes and, in strict mode, shared-operator
precedences. A fixed strict pattern has integer difference constraints in time;
the componentwise earliest schedule is integral and minimizes its timing score.
The same earliest-path calculation exactly minimizes penalized hard lateness for
a fixed route. Penalized medium/soft timing is resolved by a separate CP-SAT
model, because pairwise operator overlap still depends on integer starts.

OR-Tools MathOpt PDLP solves a continuous convex relaxation of each timing
subproblem. Squared line spans form its diagonal quadratic objective. Its dual
multipliers are converted to rational values, and the Lagrangian is minimized
over bounded timing variables before an integer GBD lower-bound cut is added.
Therefore a floating-point PDLP status by itself is never an optimality proof.
For penalized cost cuts, the relaxation omits nonnegative operator overlap; an
exact fixed-pattern CP-SAT solve supplies the missing integer recourse cost.
An infeasible strict pattern is excluded, and an exact pattern cost is activated
only for that pattern. A timed-out timing solve cannot add an exact cost cut.

The solve-wide idle clock begins on entry and resets only when a fully
reconstructed business schedule strictly improves `(hard, medium, soft)`.
Those lines are flushed immediately. Master bounds, incomplete timing solves,
and new cuts do not reset the clock. `OPTIMAL` requires closed master and
subproblem proofs; `INFEASIBLE` requires an exact strict proof. `FEASIBLE` means
a replayed schedule without a global proof, and `UNKNOWN` means neither an
incumbent nor a proof. The CLI reports cut counts and certified lower bounds
separately. Normal runs use the native data; smaller cases are for tests. No
performance advantage over the monolithic model is assumed.

Run focused checks:

```bash
python -m unittest discover -s examples/or_tools/food_packaging_gbd/tests -v
```
