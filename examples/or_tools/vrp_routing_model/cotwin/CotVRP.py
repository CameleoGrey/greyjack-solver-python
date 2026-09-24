from dataclasses import dataclass, field
from typing import Callable

from ortools.constraint_solver import pywrapcp


@dataclass
class CotVRP:
    """Solver-owned indices, model, and exact score scaling."""

    manager: pywrapcp.RoutingIndexManager
    routing: pywrapcp.RoutingModel
    location_ids: tuple[int, ...]
    customer_indices: frozenset[int]
    hard_weight: int
    medium_weight: int
    time_scale: int
    objective_bound: int
    callbacks: tuple[Callable[..., int], ...] = field(repr=False)
    mode: str = "penalized"
