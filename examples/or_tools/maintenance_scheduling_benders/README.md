# Maintenance scheduling with logic-based Benders decomposition

This standalone OR-Tools example follows **business domain → cotwin → solver →
reconstructed business schedule → independent metrics**. It uses the same demo
generator and business score as `maintenance_scheduling`, without importing that
package or GreyJack. Python 3.12 or newer and OR-Tools are required.

## Run

From the repository root:

```bash
python -m pip install -r examples/or_tools/maintenance_scheduling_benders/requirements.txt
python -m examples.or_tools.maintenance_scheduling_benders.scripts.solve_task \
  --dataset-size small --start-date 2026-09-28 --time-limit 30
```

Direct execution of `scripts/solve_task.py` also works. The default is the
native 14-job, 3-crew, 40-workday `small` dataset; `large` has 48 jobs, 5 crews,
and 80 workdays. The generator uses seed 18. If `--start-date` is omitted,
`DomainBuilder` chooses the first Monday on or after today. Use a fixed date
when comparing runs. The CLI defaults to `--mode strict`, `--workers 10`, and
`--no-improvement-seconds 30`; `--time-limit` is optional.

Strict mode requires zero hard penalty and minimizes soft penalty. Penalized mode
minimizes `(hard_penalty, soft_penalty)` lexicographically through a checked
integer weight. Both modes print each strictly better *complete* business
schedule as it is found. The idle clock starts with the solve and resets only
on such an improvement. Wall-clock limits, worker scheduling, and incomplete
subproblem searches can change the returned incumbent.

The native 48-job `large` dataset has no strict schedule: an independent exact
time-indexed feasibility check proved that every legal crew/start selection
overlaps somewhere. Use `--mode penalized` when comparing scores on this native
dataset. Its positive hard penalty is a business score, not a feasibility claim.

## Decomposition and proof

The master assigns every job to one crew and holds a lower-bound cost `theta`
for each crew. For a fixed crew's job set, a CP-SAT subproblem chooses start
workdays and minimizes that crew's source score. All score terms are
nonnegative, so adding jobs to one crew cannot lower its minimum cost. This
gives valid logic-based Benders cuts:

- An infeasible strict subset cannot be assigned together to any crew.
- For a solved subset, a certified objective lower bound applies whenever that
  subset appears on a crew. An optimal solve makes this bound exact. Per-job
  minimum date costs strengthen the cut.

The master also uses calendar-capacity bounds. For each job and date interval,
its minimum occupancy over legal starts is known. Total occupancy above one
crew's available days forces overlap cost in penalized mode and is forbidden
in strict mode. These bounds prevent the master from placing most jobs on only
one or two crews before asking the timing subproblems to solve them.

Crew IDs and names do not change scheduling constraints or costs, so certified
subproblem results and cuts are shared across crews. The master orders crew
loads to remove label symmetry. Crew-wise insertion and local moves supply
primal incumbents; they never supply a proof. The search master may temporarily
skip an assignment whose timing remains unresolved. The separate proof master
contains only valid bounds and cuts, and skips cannot establish optimality or
infeasibility. Crew solves use bounded slices of the remaining time so one
hard subset does not consume the entire run.

The master searches only for a schedule cheaper than the best reconstructed
business schedule. `OPTIMAL` means this cheaper region was proved empty using
certified cuts; `INFEASIBLE` means no strict assignment exists. `FEASIBLE` means
a valid incumbent was found without global proof. `UNKNOWN` means no incumbent
or proof was obtained. An unfinished subproblem cannot contribute an optimality
or infeasibility cut, but its certified lower bound may contribute a weaker
valid cost cut. The CLI reports capacity and subproblem cut counts separately.
It exits 0 with an assignment, 1 without one, and 2 for invalid input.

## Measured native comparison

With OR-Tools 9.15.6755, `--dataset-size large --mode penalized
--start-date 2026-09-28 --workers 10 --no-improvement-seconds 30
--time-limit 30`, three isolated runs returned:

| Solver | First incumbent | Final hard penalties | Proof status |
| --- | ---: | --- | --- |
| Benders | under 0.01 s | 28, 35, 37 | `FEASIBLE` |
| Monolithic | 9.1–9.7 s | 469, 409, 467 | `FEASIBLE` |

The Benders runs each improved their initial hard penalty of 344 and added
certified subproblem cuts. These are measurements on the native 48-job instance,
not a claim about larger datasets or optimality within 30 seconds.

## Business score and verification

The source calendar increments the date before recording a weekday; Monday
boundaries therefore start on Tuesday and include the following Monday. A job
ending beyond the listed workdays uses synthetic calendar dates. Early starts
and late ends cost one hard point per calendar day. For each unordered pair on
one crew, the source's ordered-pair loop contributes twice the positive overlap
in hard points and `2,000 × shared tags × abs(raw overlap days)` in soft points.
Consequently, separated jobs with shared tags can still incur a soft cost.
Ending before the ideal date costs one soft point; ending after it costs one
million. The domain reconstruction independently checks the returned score.

Run tests from the repository root:

```bash
python -m unittest discover -s examples/or_tools/maintenance_scheduling_benders/tests -v
```
