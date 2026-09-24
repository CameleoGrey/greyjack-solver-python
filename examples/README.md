# GreyJack examples

The examples environment uses the local GreyJack checkout through an editable
`../greyjack` dependency. GreyJack requires Python 3.10 or newer; this environment
uses Python 3.12. Install uv and rustup first. Source builds require Rust 1.95 or
newer, and the repository pins Rust 1.98.1.

Run these commands from the repository root:

```bash
uv sync --project examples --group dev
uv run --project examples python -m examples.object_oriented.employee_scheduling.scripts.solve_task
uv run --project examples --group dev python -m pytest greyjack/tests
```

For normal local development, select `examples/.venv` as the interpreter in your
IDE, edit the example or GreyJack Python source, and run the example. A Python
source edit is picked up by the next process. After changing Rust source, Cargo
dependencies, or native features, rebuild and restart the interpreter:

```bash
uv sync --project examples --group dev --reinstall-package greyjack
```

The first sync compiles GreyJack's native extension. The editable installation
does not automatically reload an already imported Rust library.

The supported native compatibility cohort is Python Polars `>=1.44.2,<1.45`,
Rust Polars `0.55.2`, `pyo3-polars 0.28.0`, and PyO3 `0.29.2`. Keep these aligned
when updating dependencies. The wheel CI tests Python 3.10 and 3.12 with Python
Polars 1.44.2; a configured workflow is not evidence of a completed remote run.
CI uses ThinLTO, 16 codegen units, no debug information, and two build jobs to
reduce build memory on hosted runners with 7 GB RAM, retaining optimization
level 3. These workflow settings do not change local release builds.

The original employee scheduling example keeps its score weights, pair counting,
and data-generation behavior. Its cotwin uses actual shift ends and calendar
start dates for interval and date constraints. Construction errors propagate to
the caller instead of returning an incomplete cotwin.

For process-based solving, run from an importable module and keep execution
inside an `if __name__ == "__main__":` guard. Agent failures raise `RuntimeError`;
normal stopping returns the best solution or `None` when none exists. Ctrl-C
cleans up and re-raises `KeyboardInterrupt`. Thread callbacks require cooperative
completion and cannot safely be forcibly stopped while blocked.

Some examples require datasets from
[GreyJack example data](https://github.com/CameleoGrey/greyjack-data-for-examples).
The employee scheduling demo generates its data locally.

The independent OR-Tools examples have their own dependency files and run guides:

- [Cloud balancing](or_tools/cloud_balancing/README.md)
- [Employee scheduling](or_tools/employee_scheduling/README.md)
- [Facility location](or_tools/facility_location/README.md)
- [Food packaging](or_tools/food_packaging/README.md)
- [Maintenance scheduling](or_tools/maintenance_scheduling/README.md)
- [Traveling salesperson with CP-SAT](or_tools/tsp_cp_sat/README.md)
- [Traveling salesperson with RoutingModel](or_tools/tsp_routing_model/README.md)
- [Vehicle routing with CP-SAT](or_tools/vrp_cp_sat/README.md)
- [Vehicle routing with RoutingModel](or_tools/vrp_routing_model/README.md)

The scheduling, location, packaging, and VRP examples accept `--mode strict` to
enforce their business requirements and optimize the remaining objective. Their
current command-line default is `strict`; use `--mode penalized` for overload or
violation-first scoring. Both TSP examples always require every stop exactly once.

They can run without installing GreyJack. Their models and execution paths are
separate from the original GreyJack examples above.
