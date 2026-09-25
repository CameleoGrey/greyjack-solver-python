from .Location import Location
from .Facility import Facility


class Consumer:
    def __init__(
        self,
        id: int,
        location: Location,
        demand: int,
        facility: "Facility | None" = None,
    ):
        self.id = id
        self.location = location
        self.demand = demand
        self._facility: Facility | None = None
        self.facility = facility

    @property
    def facility(self) -> "Facility | None":
        return self._facility

    @facility.setter
    def facility(self, value: "Facility | None") -> None:
        if value is not None and not isinstance(value, Facility):
            raise ValueError("Assigned facility must be a Facility or None")
        if value is self._facility:
            return
        if self._facility is not None:
            self._facility.consumers.remove(self)
        self._facility = value
        if value is not None:
            value.consumers.append(self)

    def is_assigned(self) -> bool:
        return self.facility is not None

    def distance_from_facility(self) -> int:
        if self.facility is None:
            raise RuntimeError("No facility is assigned.")
        return self.facility.location.get_distance_to(self.location)

    def __str__(self) -> str:
        return f"Consumer {self.id} ({self.demand} dem)"
