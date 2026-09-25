"""Business snapshot and checked facts shared by the Cross models."""

from dataclasses import dataclass

from ..domain import FacilityLocationDomain


@dataclass(frozen=True)
class CotFacilityLocation:
    domain: FacilityLocationDomain
    distances: dict[tuple[int, int], int]
    hard_weight: int
    assignment_upper: int
    setup_lower: int
    setup_upper: int
    mode: str
    use_greedy_seed: bool
