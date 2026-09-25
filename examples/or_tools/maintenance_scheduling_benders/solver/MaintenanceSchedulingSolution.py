from dataclasses import dataclass


@dataclass
class MaintenanceSchedulingSolution:
    status: str
    assignments: dict[int, tuple[int, int]] | None
    hard_penalty: int | None
    soft_penalty: int | None
    elapsed_seconds: float
    termination_reason: str
    mode: str
    iterations: int = 0
    cuts: int = 0
    capacity_cuts: int = 0
    subproblem_cuts: int = 0

    @property
    def has_solution(self) -> bool:
        return self.status in ("FEASIBLE", "OPTIMAL") and self.assignments is not None
