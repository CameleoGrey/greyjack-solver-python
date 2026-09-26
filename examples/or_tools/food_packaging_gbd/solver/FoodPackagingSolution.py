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
    iterations: int = 0
    gbd_cuts: int = 0
    pattern_cuts: int = 0
    feasibility_cuts: int = 0
    timing_solves: int = 0
    hard_lower_bound: int | None = None
    cost_lower_bound: int | None = None

    @property
    def has_solution(self) -> bool:
        return (
            self.status in ("FEASIBLE", "OPTIMAL")
            and self.line_routes is not None
            and self.start_times is not None
        )
