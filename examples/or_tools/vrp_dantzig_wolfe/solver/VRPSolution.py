from dataclasses import dataclass


@dataclass(frozen=True)
class VRPSolution:
    status: str
    routes: tuple[tuple[int, ...], ...] | None
    hard_penalty: int | None
    medium_penalty: int | None
    distance: int | None
    elapsed_seconds: float
    termination_reason: str
    lp_converged: bool = False
    restricted_master_status: str = "NOT_RUN"
    pricing_status: str = "NOT_RUN"
    column_count: int = 0
    pricing_mode: str = "fast"
    generator_score: tuple[int, int, int] | None = None
    pool_master_score: tuple[int, int, int] | None = None
    generator_seconds: float = 0.0
    pricing_seconds: float = 0.0
    master_seconds: float = 0.0

    @property
    def has_solution(self) -> bool:
        return self.status == "FEASIBLE" and self.routes is not None
