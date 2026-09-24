from dataclasses import dataclass

from ortools.sat.python import cp_model


@dataclass
class CotVRP:
    model: cp_model.CpModel
    arcs: dict[tuple[int, int, int], cp_model.IntVar]
    assigned: dict[tuple[int, int], cp_model.IntVar]
    used: dict[int, cp_model.IntVar]
    order: dict[int, cp_model.IntVar]
    overloads: dict[int, cp_model.IntVar]
    arrival: dict[int, cp_model.IntVar]
    service_start: dict[int, cp_model.IntVar]
    customer_lateness: dict[int, cp_model.IntVar]
    return_time: dict[int, cp_model.IntVar]
    vehicle_lateness: dict[int, cp_model.IntVar]
    hard_penalty: cp_model.IntVar
    medium_penalty: cp_model.IntVar
    distance: cp_model.IntVar
    location_ids: tuple[int, ...]
    customer_indices: tuple[int, ...]
    vehicle_depots: tuple[int, ...]
    medium_weight: int
    hard_weight: int
    mode: str = "penalized"
