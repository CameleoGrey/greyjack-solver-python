"""A replayed business incumbent and a valid Lagrangian lower bound."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CloudBalancingSolution:
    status: str
    assignments: dict[int, int] | None
    hard_penalty: int | None
    soft_cost: int | None
    elapsed_seconds: float
    termination_reason: str
    mode: str
    iterations: int
    dual_lower_bound: Decimal | None

    @property
    def has_solution(self) -> bool:
        return self.status in ("FEASIBLE", "OPTIMAL") and self.assignments is not None
