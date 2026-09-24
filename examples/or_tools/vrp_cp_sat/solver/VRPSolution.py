from dataclasses import dataclass


@dataclass
class VRPSolution:
    status: str
    routes: tuple[tuple[int, ...], ...] | None
    hard_penalty: int | None
    medium_penalty: int | None
    distance: int | None
    elapsed_seconds: float
    termination_reason: str

    @property
    def has_solution(self) -> bool:
        return self.status in ("FEASIBLE", "OPTIMAL") and self.routes is not None
