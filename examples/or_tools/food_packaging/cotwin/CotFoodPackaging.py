from dataclasses import dataclass
from datetime import datetime

from ortools.sat.python import cp_model


@dataclass
class CotFoodPackaging:
    model: cp_model.CpModel
    origin: datetime
    mode: str
    assignment: dict[tuple[int, int], cp_model.IntVar]
    empty_line: dict[int, cp_model.IntVar]
    arcs: dict[tuple[int, int | None, int | None], cp_model.IntVar]
    start: dict[int, cp_model.IntVar]
    end: dict[int, cp_model.IntVar]
    hard_penalty: cp_model.IntVar
    medium_penalty: cp_model.IntVar
    soft_penalty: cp_model.IntVar
    operator_overlap: cp_model.IntVar
    ideal_lateness: cp_model.IntVar
    cleaning_penalty: cp_model.IntVar
    medium_weight: int
    horizon: int
    job_ids: tuple[int, ...]
    line_ids: tuple[int, ...]
