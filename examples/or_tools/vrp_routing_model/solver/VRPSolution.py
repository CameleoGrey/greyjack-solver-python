from dataclasses import dataclass


@dataclass(frozen=True)
class VRPSolution:
    status: str
    routes: tuple[tuple[int, ...], ...] | None
    hard_penalty: int | None
    medium_penalty: int | None
    distance: int | None
    objective: int | None
    elapsed_seconds: float
    termination_reason: str

    @property
    def has_solution(self) -> bool:
        return (
            self.routes is not None
            and self.hard_penalty is not None
            and self.medium_penalty is not None
            and self.distance is not None
            and self.objective is not None
        )
