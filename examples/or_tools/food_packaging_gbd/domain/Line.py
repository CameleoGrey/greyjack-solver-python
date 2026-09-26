from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .Job import Job


@dataclass(eq=False)
class Line:
    id: int
    name: str
    operator: str
    start_date_time: datetime
    jobs: list["Job"] = field(default_factory=list, repr=False)

    def __str__(self) -> str:
        jobs = "\n".join(str(job) for job in self.jobs)
        return f"Line: {self.id} | start_date_time: {self.start_date_time}\n{jobs}"
