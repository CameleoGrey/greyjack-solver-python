from dataclasses import dataclass

from ortools.sat.python import cp_model

from ..domain import MaintenanceSchedule


@dataclass
class CotMaintenanceSchedule:
    """Crew-assignment master and immutable facts used by its subproblems."""

    domain: MaintenanceSchedule
    master: cp_model.CpModel
    assignments: dict[int, dict[int, cp_model.IntVar]]
    crew_costs: dict[int, cp_model.IntVar]
    crew_ids: tuple[int, ...]
    start_days: tuple[int, ...]
    end_days: dict[int, tuple[int, ...]]
    allowed_starts: dict[int, tuple[int, ...]]
    individual_costs: dict[int, int]
    hard_weight: int
    hard_upper_bound: int
    soft_upper_bound: int
    cost_upper_bound: int
    mode: str


@dataclass
class CotCrewSubproblem:
    """Exact timing model for one set of jobs assigned to one crew."""

    model: cp_model.CpModel
    start_variables: dict[int, cp_model.IntVar]
    hard_penalty: cp_model.IntVar
    soft_penalty: cp_model.IntVar
