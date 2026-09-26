"""Data shared by the discrete master and fixed-pattern timing subproblems."""

from dataclasses import dataclass
from datetime import datetime

from ortools.sat.python import cp_model

from ..domain.PackagingSchedule import PackagingSchedule


@dataclass(frozen=True)
class ModelFacts:
    origin: datetime
    line_start: dict[int, int]
    duration: dict[int, int]
    min_start: dict[int, int]
    ideal_end: dict[int, int]
    max_end: dict[int, int]
    cleaning: dict[tuple[int, int], int]
    horizon: int
    hard_bound: int
    medium_bound: int
    ideal_bound: int
    cleaning_bound: int
    overlap_bound: int
    soft_bound: int
    medium_weight: int


@dataclass
class CotFoodPackaging:
    domain: PackagingSchedule
    facts: ModelFacts
    mode: str
    master: cp_model.CpModel
    assignment: dict[tuple[int, int], cp_model.IntVar]
    empty_line: dict[int, cp_model.IntVar]
    arcs: dict[tuple[int, int | None, int | None], cp_model.IntVar]
    operator_before: dict[tuple[int, int], cp_model.IntVar]
    hard_floor: cp_model.IntVar
    timing_floor: cp_model.IntVar
    cleaning_cost: cp_model.LinearExprT
    use_greedy_hints: bool

    @property
    def origin(self) -> datetime:
        return self.facts.origin

    @property
    def job_ids(self) -> tuple[int, ...]:
        return tuple(job.id for job in self.domain.jobs)

    @property
    def line_ids(self) -> tuple[int, ...]:
        return tuple(line.id for line in self.domain.lines)
