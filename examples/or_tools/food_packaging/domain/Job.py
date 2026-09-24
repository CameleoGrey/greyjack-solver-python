from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .Line import Line
    from .Product import Product


@dataclass(eq=False)
class Job:
    id: int
    name: str
    product: "Product"
    duration: timedelta
    min_start_time: datetime
    ideal_end_time: datetime
    max_end_time: datetime
    priority: int = 0
    pinned: bool = False
    line: "Line | None" = field(default=None, repr=False)
    start_time: datetime | None = None
    end_time: datetime | None = None

    def __str__(self) -> str:
        return (
            f"{self.id} ({self.name}) | duration {self.duration} | "
            f"start {self.start_time} | end {self.end_time}"
        )
