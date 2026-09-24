from dataclasses import dataclass, field
from typing import Callable

from ortools.constraint_solver import pywrapcp


@dataclass
class CotTSP:
    """RoutingModel state and its original location-ID mapping."""

    manager: pywrapcp.RoutingIndexManager
    routing: pywrapcp.RoutingModel
    location_ids: tuple[int, ...]
    objective_bound: int
    callbacks: tuple[Callable[[int, int], int], ...] = field(repr=False)
