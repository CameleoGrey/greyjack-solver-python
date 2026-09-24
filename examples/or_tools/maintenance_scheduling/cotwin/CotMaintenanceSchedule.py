from dataclasses import dataclass

from ortools.sat.python import cp_model


@dataclass
class CotMaintenanceSchedule:
    model: cp_model.CpModel
    crew_variables: dict[int, cp_model.IntVar]
    start_variables: dict[int, cp_model.IntVar]
    crew_ids: tuple[int, ...]
    hard_penalty: cp_model.IntVar
    soft_penalty: cp_model.IntVar
    penalty_components: dict[str, cp_model.IntVar]
    hard_weight: int
    mode: str
