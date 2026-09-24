# Food packaging with OR-Tools

This standalone CP-SAT example preserves the object-oriented flow: business
`PackagingSchedule` → cotwin → solver → reconstructed ordered business lines →
independent metrics. Its runtime dependencies are OR-Tools and the Python
standard library; GreyJack is not required.

`strict` is the default mode. It enforces earliest job starts, latest job ends,
and nonoverlapping production for lines sharing an operator. Use
`--mode penalized` for the source's hard/medium/soft priorities, where latest-end
lateness is hard, squared line spans are medium, and operator production overlap,
ideal-end lateness, and weighted cleaning are soft. In penalized mode, earliest
starts remain unenforced as in the source. Strict mode returns no schedule if no
feasible incumbent is found; it does not switch to penalized mode.

## Run

From the repository root with Python 3.12 or newer:

```bash
python -m pip install -r examples/or_tools/food_packaging/requirements.txt
python -m examples.or_tools.food_packaging.scripts.solve_task --time-limit 60 --no-schedule
```

Direct execution works from any working directory:

```bash
python /path/to/greyjack-solver-python/examples/or_tools/food_packaging/scripts/solve_task.py \
  --line-count 2 --job-count 8 --start-date 2026-09-28 --workers 1
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--line-count` | `5` | Number of generated lines |
| `--job-count` | `100` | Number of generated jobs |
| `--seed` | `37` | Demo random seed |
| `--start-date` | Next Monday after today | Explicit `YYYY-MM-DD` planning start |
| `--mode` | `strict` | `strict` constraints or `penalized` scoring |
| `--workers` | `10` | CP-SAT workers |
| `--no-improvement-seconds` | `15` | Idle cutoff after the last improving incumbent |
| `--time-limit` | None | Optional total search limit in seconds |
| `--no-greedy-hints` | Off | Disable advisory earliest-deadline hints |
| `--no-schedule` | Off | Print metrics without every scheduled job |

The default generator retains 60 products, five lines, 100 jobs, and the source's
directional product-cleaning matrix. Supplying both `--seed` and `--start-date`
reproduces generated facts. The 5×100 CP-SAT model is large; a bounded search may
return `FEASIBLE` without proving optimality, or `UNKNOWN` without an incumbent.
Use a smaller job count for quick experiments. The CLI exits with code 0 for an
assignment, 1 for no assignment, and 2 for invalid input/configuration.

## Domain, model, and score

`domain` contains `Product`, `Line`, `Job`, and `PackagingSchedule` without
OR-Tools imports. `persistence` generates business facts, constructs the cotwin,
and rebuilds a copy of the business schedule by actual IDs. `cotwin` holds the
CP-SAT model and variable mappings. `solver` returns ordered line routes, actual
production starts, scores, status, and termination reason.

```python
from datetime import date

from examples.or_tools.food_packaging.persistence.DomainBuilder import DomainBuilder
from examples.or_tools.food_packaging.persistence.CotwinBuilder import CotwinBuilder
from examples.or_tools.food_packaging.solver.FoodPackagingSolver import FoodPackagingSolver

builder = DomainBuilder(line_count=2, job_count=8, start_date=date(2026, 9, 28))
domain = builder.build_domain_from_scratch()
cotwin = CotwinBuilder(mode="strict").build_cotwin(domain)
solution = FoodPackagingSolver(workers=1, time_limit=30).solve(cotwin)
if solution.has_solution:
    solved = builder.build_from_solution(solution, initial_domain=domain)
    solved.print_schedule()
    solved.print_metrics()
else:
    print(solution.status, solution.termination_reason)
```

Each job belongs to exactly one line and has one position in its ordered route.
The first job can start no earlier than its line's start. An incoming job starts
after its predecessor finishes **and** its own product's cleaning duration from
the predecessor's product. CP-SAT uses minute offsets from the earliest business
timestamp, retaining the full hour and minute of all deadlines.

For each completed schedule:

```text
hard   = sum(max(0, job_end - latest_end)) in minutes
medium = sum((last_job_end - line_start)^2) over nonempty lines
soft   = sum(pairwise production overlap for jobs with one operator)
       + sum(max(0, job_end - ideal_end)) in minutes
       + sum(incoming_job.priority * cleaning_before_incoming_job)
```

The source also penalizes duplicate line positions, which the circuit model
excludes by construction. Strict mode enforces zero hard lateness, zero early
starts, and zero operator production overlap, then minimizes medium before soft.
Cleaning itself is not reserved on the operator; it delays the next job on its
line. Penalized mode first minimizes hard lateness, then fixes the proven best
hard score and minimizes a safely weighted medium/soft objective. A bounded
incumbent without proof is reported as `FEASIBLE`.

The source scorer omitted the first job's production end, truncated deadlines to
midnight, and applied product-change cleaning after the incoming job. This port
repairs those timeline calculations. The original generator's Timefold/Apache
attribution is retained in `DemoDataGenerator.py`. The source's `pinned` flag is
unimplemented; this port rejects pinned jobs rather than moving them silently.

Reconstruction verifies exact coverage, line order, cleaning precedence, job
durations, operator overlaps, and all score components from business objects.
The solver prints and flushes each lexicographically improving score tuple. A
watchdog stops searches with no new callback, and unsafe CP-SAT integer bounds
are rejected before search.

Run tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/food_packaging/tests -v
```
