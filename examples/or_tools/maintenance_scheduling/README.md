# Maintenance scheduling with OR-Tools

This standalone CP-SAT example follows **business domain → cotwin → solver →
reconstructed business schedule → independent metrics**. It requires Python 3.12
or newer and OR-Tools, and does not import GreyJack. The demo generator is ported
from the object-oriented maintenance example; its original upstream inspiration
is the Timefold demo (Apache-2.0).

## Run

From the repository root:

```bash
python -m pip install -r examples/or_tools/maintenance_scheduling/requirements.txt
python -m examples.or_tools.maintenance_scheduling.scripts.solve_task \
  --dataset-size small --start-date 2026-09-28 --time-limit 30
```

Direct execution also works from any directory:

```bash
python /path/to/greyjack-solver-python/examples/or_tools/maintenance_scheduling/scripts/solve_task.py \
  --dataset-size small --mode penalized --start-date 2026-09-28
```

The CLI defaults to the 14-job, 3-crew, 40-workday `small` dataset. `large` has
48 jobs, 5 crews, and 80 workdays. The generator uses the source's fixed random
seed 18. When `--start-date` is omitted, the first Monday on or after today is
resolved once by `DomainBuilder`. Specify a date for reproducible data. Other
options are `--workers` (default 10), `--no-improvement-seconds` (default 30),
and optional `--time-limit` in seconds. `--help` needs no OR-Tools import.

`--mode strict` is the default. It requires a zero hard score and minimizes the
source soft score; an infeasible strict instance returns no assignment.
`--mode penalized` minimizes hard score first, then soft score. The tag cost is
soft in both modes. `OPTIMAL` proves the modeled objective; `FEASIBLE` is an
incumbent without that proof. Each strictly improving incumbent is printed and
flushed. The CLI exits with code 0 for an assignment, 1 when none is returned,
and 2 for invalid input.

## Domain and cotwin

`DomainBuilder(dataset_size="small", start_date=...)` creates the business
schedule. `CotwinBuilder(mode="strict").build_cotwin(domain)` builds the CP-SAT
model. `MaintenanceSchedulingSolver(workers=10,
no_improvement_seconds=30).solve(cotwin)` returns assignments keyed by stable
job IDs; each value is `(crew_id, start_date_id)`. `DomainBuilder.build_from_solution`
copies the original schedule, applies assignments by job ID, and rejects scores
that disagree with `MaintenanceSchedule.calculate_metrics()`. That metrics method
uses only business objects and Python's standard library.

The port deliberately retains two surprising source rules:

- `WorkCalendar` increments the date before recording a weekday. A period whose
  boundaries are Mondays therefore starts on Tuesday and includes the following
  Monday. A job ending beyond the workday list uses the last listed date plus
  the number of days beyond the list, not additional workdays.
- For each **unordered** pair of jobs on the same crew, the source's ordered-pair
  loop gives `2 × max(0, raw_overlap_days)` hard points and
  `2,000 × shared_tag_count × abs(raw_overlap_days)` soft points, where
  `raw_overlap_days = min(end_a, end_b) − max(start_a, start_b)`. Thus separated
  same-tag jobs on one crew can have a tag cost. Jobs on different crews have no
  pair cost, even when their tags match.

For each job, starting before `min_start_date` costs one hard point per calendar
day; ending after `max_end_date` costs one hard point per calendar day. Ending
before `ideal_end_date` costs one soft point and ending after it costs one million
soft points. Equality has no ideal-date penalty. Optional boundary dates are
ignored when absent. The CP-SAT objective uses a checked integer weight that
makes one hard point outweigh every possible soft-score change.

The solver is seeded with zero, but parallel search and wall-clock limits can
produce different incumbents. The large model has a term for each job pair and
may be substantially slower than the small demo. For the generated large
instance starting 2026-09-28, a 30-second, 10-worker strict run returned
`UNKNOWN` without an incumbent on one local machine; that is not a proof of
infeasibility. Use a longer limit or `--mode penalized` when exploring it. A
zero hard score means the source's hard rules hold; it does not mean tag cost is
zero.

Run the standalone tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/maintenance_scheduling/tests -v
```
