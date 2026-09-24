from dataclasses import dataclass
from datetime import datetime


@dataclass
class Shift:
    """A shift with a stable ID and an optional index into schedule.employees."""

    id: int
    start: datetime
    end: datetime
    location: str
    required_skill: str
    employee: int | None = None

    def __str__(self) -> str:
        return (
            f"{self.id}: {self.start} - {self.end} "
            f"at {self.location} ({self.required_skill})"
        )
