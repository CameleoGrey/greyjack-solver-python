from dataclasses import dataclass

from ortools.sat.python import cp_model


@dataclass
class CotTSP:
    model: cp_model.CpModel
    arcs: dict[tuple[int, int], cp_model.IntVar]
    order: dict[int, cp_model.IntVar]
    distance: cp_model.IntVar
    location_ids: tuple[int, ...]
