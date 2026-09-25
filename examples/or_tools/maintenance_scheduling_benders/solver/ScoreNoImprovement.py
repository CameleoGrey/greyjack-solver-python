"""Track complete business incumbents across all Benders iterations."""

from time import monotonic


class ScoreNoImprovement:
    def __init__(self, started_at: float, seconds: float) -> None:
        self.started_at = started_at
        self.seconds = seconds
        self.deadline = started_at + seconds
        self.best_score: tuple[int, int] | None = None
        self.best_assignments: dict[int, tuple[int, int]] | None = None
        self.sequence = 0

    def record(
        self, score: tuple[int, int], assignments: dict[int, tuple[int, int]]
    ) -> bool:
        if self.best_score is not None and score >= self.best_score:
            return False
        now = monotonic()
        self.best_score = score
        self.best_assignments = assignments.copy()
        self.sequence += 1
        self.deadline = now + self.seconds
        print(
            f"[{now - self.started_at:.3f}s] New best solution "
            f"#{self.sequence}: hard_penalty={score[0]}, soft_penalty={score[1]}",
            flush=True,
        )
        return True
