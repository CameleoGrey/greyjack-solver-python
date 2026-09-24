from dataclasses import dataclass
from typing import Optional


@dataclass
class CloudBalancingSolution:
    status: str
    assignments: Optional[dict[int, int]]
    hard_penalty: Optional[int]
    soft_cost: Optional[int]
    elapsed_seconds: float
    termination_reason: str

    @property
    def has_solution(self) -> bool:
        return self.status in ("FEASIBLE", "OPTIMAL") and self.assignments is not None
