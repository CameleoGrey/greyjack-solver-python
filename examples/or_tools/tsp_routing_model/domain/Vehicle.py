from dataclasses import dataclass

from .Location import Location


@dataclass
class Vehicle:
    depot_id: int
    trip_path: list[Location] | None = None
