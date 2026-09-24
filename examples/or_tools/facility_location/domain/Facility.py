from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .Location import Location

if TYPE_CHECKING:
    from .Consumer import Consumer


@dataclass(eq=False)
class Facility:
    id: int
    location: Location
    setup_cost: int
    capacity: int
    consumers: list["Consumer"] = field(default_factory=list, repr=False)

    def get_used_capacity(self) -> int:
        return sum(consumer.demand for consumer in self.consumers)

    def is_used(self) -> bool:
        return bool(self.consumers)

    def __str__(self) -> str:
        return f"Facility {self.id} (${self.setup_cost}, {self.capacity} cap)"
