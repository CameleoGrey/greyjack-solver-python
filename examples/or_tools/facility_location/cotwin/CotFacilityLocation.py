from dataclasses import dataclass

from ortools.sat.python import cp_model


@dataclass
class CotFacilityLocation:
    model: cp_model.CpModel
    assignment_variables: dict[int, dict[int, cp_model.IntVar]]
    facility_used: dict[int, cp_model.IntVar]
    facility_load: dict[int, cp_model.IntVar]
    facility_overload: dict[int, cp_model.IntVar]
    hard_penalty: cp_model.IntVar
    soft_cost: cp_model.IntVar
    hard_weight: int
    mode: str
