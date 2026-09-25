from dataclasses import dataclass
from datetime import date


@dataclass
class Job:
    job_id: int
    name: str
    duration_in_days: int
    min_start_date: date | None
    max_end_date: date | None
    ideal_end_date: date | None
    tags: tuple[str, ...]
    crew_id: int | None = None
    start_date_id: int | None = None
