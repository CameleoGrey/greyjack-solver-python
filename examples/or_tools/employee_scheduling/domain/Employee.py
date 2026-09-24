from dataclasses import dataclass, field
from datetime import date


@dataclass
class Employee:
    """Business employee; date preferences apply to a shift's start date."""

    name: str
    skills: list[str]
    unavailable_dates: list[date] = field(default_factory=list)
    undesired_dates: list[date] = field(default_factory=list)
    desired_dates: list[date] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"{self.name} ({self.skills}) | "
            f"Unavailable dates {self.unavailable_dates} | "
            f"Undesired dates {self.undesired_dates} | "
            f"Desired dates {self.desired_dates}"
        )
