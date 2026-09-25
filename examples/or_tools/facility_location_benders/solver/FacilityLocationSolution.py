from dataclasses import dataclass


@dataclass
class FacilityLocationSolution:
    status: str
    assignments: dict[int, int] | None
    hard_penalty: int | None
    soft_cost: int | None
    elapsed_seconds: float
    termination_reason: str
    mode: str
    iterations: int
    optimality_cuts: int
    feasibility_cuts: int
    lower_bound: int | None

    @property
    def has_solution(self) -> bool:
        return self.status in ("FEASIBLE", "OPTIMAL") and self.assignments is not None
