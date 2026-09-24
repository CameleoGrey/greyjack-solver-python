from dataclasses import dataclass


@dataclass
class EmployeeSchedulingSolution:
    status: str
    assignments: dict[int, int] | None
    hard_penalty: int | None
    soft_penalty_cents: int | None
    elapsed_seconds: float
    termination_reason: str

    @property
    def has_solution(self) -> bool:
        return self.status in ("FEASIBLE", "OPTIMAL") and self.assignments is not None
