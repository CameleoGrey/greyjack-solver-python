"""A separable GLOP model and the business data used to replay assignments."""

from dataclasses import dataclass

from ortools.linear_solver import pywraplp

from ..domain.ScheduleCB import ScheduleCB


@dataclass
class DemandGroup:
    requirements: tuple[int, int, int]
    process_ids: tuple[int, ...]
    choices: dict[int, pywraplp.Variable]


@dataclass
class CotScheduleCB:
    domain: ScheduleCB
    model: pywraplp.Solver
    groups: tuple[DemandGroup, ...]
    activation: dict[int, pywraplp.Variable]
    mode: str
    hard_weight: int
    use_greedy_seed: bool

    @property
    def process_count(self) -> int:
        return len(self.domain.processes)
