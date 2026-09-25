"""Validated business snapshot and the Benders master model."""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from ..domain import FacilityLocationDomain


@dataclass
class CotFacilityLocation:
    domain: FacilityLocationDomain
    master: cp_model.CpModel
    openings: dict[int, cp_model.IntVar]
    assignment_cost: cp_model.IntVar
    distances: dict[tuple[int, int], int]
    hard_weight: int
    assignment_upper: int
    mode: str
    use_greedy_seed: bool
