from dataclasses import dataclass, field
from typing import Any

from .Consumer import Consumer
from .Facility import Facility
from .Location import Location


@dataclass
class FacilityLocationDomain:
    facilities: list[Facility] = field(default_factory=list)
    consumers: list[Consumer] = field(default_factory=list)
    south_west_corner: Location | None = None
    north_east_corner: Location | None = None

    @classmethod
    def empty(cls) -> "FacilityLocationDomain":
        return cls([], [], Location(-90, -180), Location(90, 180))

    def get_bounds(self) -> list[Location | None]:
        return [self.south_west_corner, self.north_east_corner]

    def validate(self) -> None:
        facility_ids: set[int] = set()
        for facility in self.facilities:
            if type(facility.id) is not int or facility.id in facility_ids:
                raise ValueError(f"Invalid or duplicate facility ID: {facility.id!r}")
            facility_ids.add(facility.id)
            if not isinstance(facility.location, Location):
                raise ValueError(f"Facility {facility.id} has no valid location")
            facility.location.validate()
            if type(facility.setup_cost) is not int:
                raise ValueError(
                    f"Facility {facility.id} setup cost must be an integer"
                )
            if type(facility.capacity) is not int or facility.capacity < 0:
                raise ValueError(f"Facility {facility.id} capacity must be nonnegative")

        if self.consumers and not self.facilities:
            raise ValueError("Cannot assign consumers without facilities")
        consumer_ids: set[int] = set()
        known_facilities = {id(facility) for facility in self.facilities}
        for consumer in self.consumers:
            if type(consumer.id) is not int or consumer.id in consumer_ids:
                raise ValueError(f"Invalid or duplicate consumer ID: {consumer.id!r}")
            consumer_ids.add(consumer.id)
            if not isinstance(consumer.location, Location):
                raise ValueError(f"Consumer {consumer.id} has no valid location")
            consumer.location.validate()
            if type(consumer.demand) is not int or consumer.demand < 0:
                raise ValueError(f"Consumer {consumer.id} demand must be nonnegative")
            if (
                consumer.facility is not None
                and id(consumer.facility) not in known_facilities
            ):
                raise ValueError(f"Consumer {consumer.id} references unknown facility")

        for corner in (self.south_west_corner, self.north_east_corner):
            if corner is not None:
                if not isinstance(corner, Location):
                    raise ValueError("Domain bounds must contain locations")
                corner.validate()

    def calculate_metrics(self) -> dict[str, Any]:
        """Replay a complete assignment using only business objects."""
        self.validate()
        usage = {facility.id: 0 for facility in self.facilities}
        counts = {facility.id: 0 for facility in self.facilities}
        distance = 0
        for consumer in self.consumers:
            if consumer.facility is None:
                raise ValueError(f"Consumer {consumer.id} is unassigned")
            fid = consumer.facility.id
            usage[fid] += consumer.demand
            counts[fid] += 1
            distance += consumer.distance_from_facility()

        setup_cost = sum(
            facility.setup_cost for facility in self.facilities if counts[facility.id]
        )
        overload_by_facility = {
            facility.id: max(0, usage[facility.id] - facility.capacity)
            for facility in self.facilities
        }
        hard_penalty = sum(overload_by_facility.values())
        soft_cost = 2 * setup_cost + 5 * distance
        return {
            "facility_usage": usage,
            "facility_consumer_counts": counts,
            "overload_by_facility": overload_by_facility,
            "facilities_used": sum(bool(count) for count in counts.values()),
            "total_distance_m": distance,
            "total_setup_cost": setup_cost,
            "hard_penalty": hard_penalty,
            "soft_cost": soft_cost,
            "capacity_feasible": hard_penalty == 0,
        }

    def get_total_cost(self) -> int:
        return sum(
            facility.setup_cost for facility in self.facilities if facility.is_used()
        )

    def get_potential_cost(self) -> int:
        return sum(facility.setup_cost for facility in self.facilities)

    def get_total_distance(self) -> str:
        distance = sum(
            consumer.distance_from_facility()
            for consumer in self.consumers
            if consumer.is_assigned()
        )
        return f"{distance // 1000} km"

    def print_metrics(self) -> None:
        metrics = self.calculate_metrics()
        print("Facility usages:")
        for facility in self.facilities:
            if metrics["facility_consumer_counts"][facility.id]:
                print(
                    f"{facility.id}: {metrics['facility_usage'][facility.id]}/"
                    f"{facility.capacity}"
                )
        print(f"Facilities used: {metrics['facilities_used']}")
        print(f"Total distance: {metrics['total_distance_m']} m")
        print(f"Total setup cost: {metrics['total_setup_cost']}$")
        print(f"Hard penalty (total overload): {metrics['hard_penalty']}")
        print(f"Soft cost (2*setup + 5*distance): {metrics['soft_cost']}")
        print(f"Capacity feasible: {metrics['capacity_feasible']}")

    def __str__(self) -> str:
        return (
            f"FacilityLocationProblem{{facilities: {len(self.facilities)}, "
            f"consumers: {len(self.consumers)}}}"
        )
