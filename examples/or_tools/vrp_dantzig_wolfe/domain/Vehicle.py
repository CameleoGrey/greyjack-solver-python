from dataclasses import dataclass, field

from .Customer import Customer


@dataclass
class Vehicle:
    depot_id: int
    capacity: int
    work_day_start: int | None = None
    work_day_end: int | None = None
    customer_list: list[Customer] = field(default_factory=list)
