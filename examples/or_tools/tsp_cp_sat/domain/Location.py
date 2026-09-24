from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    id: int
    name: str
    latitude: float
    longitude: float
