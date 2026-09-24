from dataclasses import dataclass

from ortools.sat.python import cp_model

from ..cotwin import CotTSP
from ..domain import TravelSchedule


@dataclass(frozen=True)
class _ModelFacts:
    location_ids: tuple[int, ...]
    distance_bound: int


class CotwinBuilder:
    def __init__(self, use_greedy_hints: bool = True):
        self.use_greedy_hints = use_greedy_hints

    def build_cotwin(self, domain: TravelSchedule) -> CotTSP:
        domain.validate()
        facts = self._checked_model_facts(domain)
        location_count = len(facts.location_ids)
        model = cp_model.CpModel()
        arcs, order = self._add_route_variables(model, location_count)
        self._add_route_constraints(model, arcs, order, location_count)
        distance = self._add_objective(
            model, domain.distance_matrix, arcs, facts.distance_bound
        )

        cotwin = CotTSP(model, arcs, order, distance, facts.location_ids)
        if self.use_greedy_hints:
            self._add_greedy_hints(domain, cotwin)
        validation_error = model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        return cotwin

    @staticmethod
    def _checked_model_facts(domain: TravelSchedule) -> _ModelFacts:
        location_ids = tuple(location.id for location in domain.locations_list)
        max_distance = max(max(row) for row in domain.distance_matrix)
        distance_bound = len(location_ids) * max_distance
        if distance_bound > cp_model.INT_MAX // 2:
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")
        return _ModelFacts(location_ids, distance_bound)

    @staticmethod
    def _add_route_variables(
        model: cp_model.CpModel, location_count: int
    ) -> tuple[dict[tuple[int, int], cp_model.IntVar], dict[int, cp_model.IntVar]]:
        arcs = {
            (source, target): model.new_bool_var(f"arc_{source}_{target}")
            for source in range(location_count)
            for target in range(location_count)
            if source != target
        }
        order = {
            index: model.new_int_var(1, location_count - 1, f"order_{index}")
            for index in range(1, location_count)
        }
        return arcs, order

    @staticmethod
    def _add_route_constraints(
        model: cp_model.CpModel,
        arcs: dict[tuple[int, int], cp_model.IntVar],
        order: dict[int, cp_model.IntVar],
        location_count: int,
    ) -> None:
        for index in range(location_count):
            model.add_exactly_one(
                arcs[index, target]
                for target in range(location_count)
                if target != index
            )
            model.add_exactly_one(
                arcs[source, index]
                for source in range(location_count)
                if source != index
            )

        # Rising order on chosen non-depot arcs rules out disconnected subtours.
        for source in range(1, location_count):
            for target in range(1, location_count):
                if source != target:
                    model.add(order[target] >= order[source] + 1).only_enforce_if(
                        arcs[source, target]
                    )

    @staticmethod
    def _add_objective(
        model: cp_model.CpModel,
        distance_matrix: list[list[int]],
        arcs: dict[tuple[int, int], cp_model.IntVar],
        distance_bound: int,
    ) -> cp_model.IntVar:
        distance = model.new_int_var(0, distance_bound, "distance")
        model.add(
            distance
            == sum(
                distance_matrix[source][target] * arc
                for (source, target), arc in arcs.items()
            )
        )
        model.minimize(distance)
        return distance

    @staticmethod
    def _add_greedy_hints(domain: TravelSchedule, cotwin: CotTSP) -> None:
        matrix = domain.distance_matrix
        unvisited = set(range(1, len(domain.locations_list)))
        route = [0]
        while unvisited:
            current = route[-1]
            next_index = min(
                unvisited, key=lambda index: (matrix[current][index], index)
            )
            route.append(next_index)
            unvisited.remove(next_index)
        route.append(0)
        selected_arcs = set(zip(route, route[1:]))
        for edge, variable in cotwin.arcs.items():
            cotwin.model.add_hint(variable, int(edge in selected_arcs))
        for position, index in enumerate(route[1:-1], 1):
            cotwin.model.add_hint(cotwin.order[index], position)
        cotwin.model.add_hint(
            cotwin.distance,
            sum(matrix[source][target] for source, target in selected_arcs),
        )
