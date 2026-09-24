from dataclasses import dataclass


@dataclass(frozen=True)
class Customer:
    """A location; depots use the same source record as delivery customers."""

    id: int
    name: str
    latitude: float
    longitude: float
    demand: int
    time_window_start: int | None = None
    time_window_end: int | None = None
    service_time: int | None = None
