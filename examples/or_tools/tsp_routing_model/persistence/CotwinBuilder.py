from dataclasses import dataclass
from typing import Callable

from ortools.constraint_solver import pywrapcp

from ..cotwin import CotTSP
from ..domain import TravelSchedule


@dataclass(frozen=True)
class _RoutingFacts:
    location_ids: tuple[int, ...]
    matrix: tuple[tuple[int, ...], ...]
    objective_bound: int


class CotwinBuilder:
    """Translate a validated business schedule to a one-vehicle RoutingModel."""

    def build_cotwin(self, domain: TravelSchedule) -> CotTSP:
        domain.validate()
        facts = self._checked_routing_facts(domain)
        manager = pywrapcp.RoutingIndexManager(len(facts.location_ids), 1, 0)
        routing = pywrapcp.RoutingModel(manager)
        distance_callback = self._add_distance_cost(routing, manager, facts.matrix)
        return CotTSP(
            manager,
            routing,
            facts.location_ids,
            facts.objective_bound,
            (distance_callback,),
        )

    @staticmethod
    def _checked_routing_facts(domain: TravelSchedule) -> _RoutingFacts:
        location_ids = tuple(location.id for location in domain.locations_list)
        matrix = tuple(tuple(row) for row in domain.distance_matrix)
        max_distance = max(max(row) for row in matrix)
        objective_bound = len(location_ids) * max_distance
        safe_bound = ((1 << 63) - 1) // 4
        if objective_bound > safe_bound:
            raise ValueError("Dataset exceeds safe RoutingModel integer bounds")
        return _RoutingFacts(location_ids, matrix, objective_bound)

    @staticmethod
    def _add_distance_cost(
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        matrix: tuple[tuple[int, ...], ...],
    ) -> Callable[[int, int], int]:
        def distance_callback(source: int, target: int) -> int:
            return matrix[manager.IndexToNode(source)][manager.IndexToNode(target)]

        callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(callback_index)
        return distance_callback
