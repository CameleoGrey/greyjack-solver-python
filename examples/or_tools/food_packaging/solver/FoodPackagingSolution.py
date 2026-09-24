from dataclasses import dataclass
from datetime import datetime


@dataclass
class FoodPackagingSolution:
    status: str
    line_routes: dict[int, tuple[int, ...]] | None
    start_times: dict[int, datetime] | None
    hard_penalty: int | None
    medium_penalty: int | None
    soft_penalty: int | None
    elapsed_seconds: float
    termination_reason: str
    mode: str

    @property
    def has_solution(self) -> bool:
        return (
            self.status in ("FEASIBLE", "OPTIMAL")
            and self.line_routes is not None
            and self.start_times is not None
        )
