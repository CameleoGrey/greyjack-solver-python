from ortools.sat.python import cp_model

from ..cotwin.CotFacilityLocation import CotFacilityLocation
from ..domain.FacilityLocationDomain import FacilityLocationDomain


class CotwinBuilder:
    def __init__(self, *, mode: str = "strict", use_greedy_hints: bool = True):
        if mode not in ("strict", "penalized"):
            raise ValueError("mode must be 'strict' or 'penalized'")
        self.mode = mode
        self.use_greedy_hints = use_greedy_hints

    def build_cotwin(self, domain: FacilityLocationDomain) -> CotFacilityLocation:
        domain.validate()
        total_demand = sum(consumer.demand for consumer in domain.consumers)
        distances = {
            (consumer.id, facility.id): consumer.location.get_distance_to(
                facility.location
            )
            for consumer in domain.consumers
            for facility in domain.facilities
        }
        setup_lower = 2 * sum(min(0, f.setup_cost) for f in domain.facilities)
        setup_upper = 2 * sum(max(0, f.setup_cost) for f in domain.facilities)
        distance_upper = 5 * sum(
            max(distances[consumer.id, facility.id] for facility in domain.facilities)
            for consumer in domain.consumers
        )
        soft_lower = setup_lower
        soft_upper = setup_upper + distance_upper
        hard_weight = soft_upper - soft_lower + 1 if self.mode == "penalized" else 0

        # Keep all coefficients, variable domains, and total objectives well inside
        # OR-Tools' signed 64-bit range, including the weighted penalized model.
        safe_bound = cp_model.INT_MAX // 2
        bounds = [
            total_demand,
            abs(soft_lower),
            abs(soft_upper),
            *(abs(f.capacity) for f in domain.facilities),
            *(abs(2 * f.setup_cost) for f in domain.facilities),
            *(5 * distance for distance in distances.values()),
        ]
        if self.mode == "penalized":
            bounds.extend((hard_weight, hard_weight * total_demand + soft_upper))
        if any(value > safe_bound for value in bounds):
            raise ValueError("Dataset exceeds safe CP-SAT integer bounds")

        model = cp_model.CpModel()
        assignment_variables = {}
        for consumer in domain.consumers:
            row = {
                facility.id: model.new_bool_var(f"assign_{consumer.id}_{facility.id}")
                for facility in domain.facilities
            }
            model.add_exactly_one(row.values())
            assignment_variables[consumer.id] = row

        facility_used = {}
        facility_load = {}
        facility_overload = {}
        for facility in domain.facilities:
            fid = facility.id
            column = [
                assignment_variables[consumer.id][fid] for consumer in domain.consumers
            ]
            used = model.new_bool_var(f"used_{fid}")
            if column:
                model.add_max_equality(used, column)
            else:
                model.add(used == 0)
            facility_used[fid] = used

            load = model.new_int_var(0, total_demand, f"load_{fid}")
            model.add(
                load
                == sum(
                    consumer.demand * assignment_variables[consumer.id][fid]
                    for consumer in domain.consumers
                )
            )
            facility_load[fid] = load
            overload = model.new_int_var(
                0, max(0, total_demand - facility.capacity), f"overload_{fid}"
            )
            model.add_max_equality(overload, [0, load - facility.capacity])
            facility_overload[fid] = overload
            if self.mode == "strict":
                model.add(load <= facility.capacity)

        hard_penalty = model.new_int_var(0, total_demand, "hard_penalty")
        model.add(hard_penalty == sum(facility_overload.values()))
        soft_cost = model.new_int_var(soft_lower, soft_upper, "soft_cost")
        model.add(
            soft_cost
            == sum(2 * f.setup_cost * facility_used[f.id] for f in domain.facilities)
            + sum(
                5
                * distances[consumer.id, facility.id]
                * assignment_variables[consumer.id][facility.id]
                for consumer in domain.consumers
                for facility in domain.facilities
            )
        )
        if self.mode == "strict":
            model.add(hard_penalty == 0)
            model.minimize(soft_cost)
        else:
            model.minimize(hard_weight * hard_penalty + soft_cost)

        cotwin = CotFacilityLocation(
            model,
            assignment_variables,
            facility_used,
            facility_load,
            facility_overload,
            hard_penalty,
            soft_cost,
            hard_weight,
            self.mode,
        )
        if self.use_greedy_hints:
            self._add_greedy_hints(domain, cotwin, distances)
        validation_error = model.validate()
        if validation_error:
            raise ValueError(f"Invalid CP-SAT model: {validation_error}")
        return cotwin

    def _add_greedy_hints(
        self,
        domain: FacilityLocationDomain,
        cotwin: CotFacilityLocation,
        distances: dict[tuple[int, int], int],
    ) -> None:
        loads = {facility.id: 0 for facility in domain.facilities}
        used: set[int] = set()
        chosen: dict[int, int] = {}
        for consumer in domain.consumers:
            candidates = domain.facilities
            if self.mode == "strict":
                candidates = [
                    f for f in candidates if loads[f.id] + consumer.demand <= f.capacity
                ]
                if not candidates:
                    return  # A partial or infeasible hint does not help strict search.

            def incremental_cost(facility):
                fid = facility.id
                old_overload = max(0, loads[fid] - facility.capacity)
                new_overload = max(0, loads[fid] + consumer.demand - facility.capacity)
                hard_increase = new_overload - old_overload
                soft_increase = 5 * distances[consumer.id, fid]
                if fid not in used:
                    soft_increase += 2 * facility.setup_cost
                return (
                    cotwin.hard_weight * hard_increase + soft_increase,
                    fid,
                )

            selected = min(candidates, key=incremental_cost)
            chosen[consumer.id] = selected.id
            loads[selected.id] += consumer.demand
            used.add(selected.id)

        for consumer in domain.consumers:
            selected = chosen[consumer.id]
            for fid, variable in cotwin.assignment_variables[consumer.id].items():
                cotwin.model.add_hint(variable, int(fid == selected))
        for facility in domain.facilities:
            fid = facility.id
            cotwin.model.add_hint(cotwin.facility_used[fid], int(fid in used))
            cotwin.model.add_hint(cotwin.facility_load[fid], loads[fid])
            cotwin.model.add_hint(
                cotwin.facility_overload[fid], max(0, loads[fid] - facility.capacity)
            )
        hard = sum(max(0, loads[f.id] - f.capacity) for f in domain.facilities)
        soft = sum(2 * f.setup_cost for f in domain.facilities if f.id in used)
        soft += sum(
            5 * distances[consumer.id, chosen[consumer.id]]
            for consumer in domain.consumers
        )
        cotwin.model.add_hint(cotwin.hard_penalty, hard)
        cotwin.model.add_hint(cotwin.soft_cost, soft)
