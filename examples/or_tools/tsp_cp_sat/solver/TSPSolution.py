from dataclasses import dataclass


@dataclass
class TSPSolution:
    status: str
    tour_ids: tuple[int, ...] | None
    distance: int | None
    elapsed_seconds: float
    termination_reason: str

    @property
    def has_solution(self) -> bool:
        return (
            self.status in ("FEASIBLE", "OPTIMAL")
            and self.tour_ids is not None
            and self.distance is not None
        )
