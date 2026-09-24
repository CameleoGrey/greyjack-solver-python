"""Port of the source example's demo generator, adapted from Timefold (Apache-2.0)."""

from datetime import date, timedelta
from random import Random

from ..domain import Crew, Job, MaintenanceSchedule, WorkCalendar


def generate_demo_data(dataset_size: str, start_date: date) -> MaintenanceSchedule:
    if dataset_size not in ("small", "large"):
        raise ValueError('dataset_size must be "small" or "large"')
    crews = [
        Crew(0, "Alpha crew"),
        Crew(1, "Beta crew"),
        Crew(2, "Gamma crew"),
    ]
    if dataset_size == "large":
        crews.extend((Crew(3, "Delta crew"), Crew(4, "Epsilon crew")))
    weeks = 16 if dataset_size == "large" else 8
    calendar = WorkCalendar(0, start_date, start_date + timedelta(weeks=weeks))
    workday_total = weeks * 5
    area_names = (
        "Downtown",
        "Uptown",
        "Park",
        "Airport",
        "Bay",
        "Hill",
        "Forest",
        "Station",
        "Hospital",
        "Harbor",
        "Market",
        "Fort",
        "Beach",
        "Garden",
        "River",
        "Springs",
        "Tower",
        "Mountain",
    )
    target_names = (
        "Street",
        "Bridge",
        "Tunnel",
        "Highway",
        "Boulevard",
        "Avenue",
        "Square",
        "Plaza",
    )
    target_limit = min(len(target_names), len(crews) * 2)
    job_count = weeks * len(crews) * 3 // 5
    random = Random(18)
    jobs = []
    for i in range(job_count):
        area = area_names[i // target_limit]
        target = target_names[i % target_limit]
        duration = 1 + random.randint(0, 9)
        flexibility = duration + 5 + random.randint(0, workday_total - (duration + 5))
        min_offset = random.randint(0, workday_total - flexibility)
        ideal_offset = flexibility - 1 - random.randint(0, 3)
        min_start = start_date + timedelta(days=min_offset)
        max_end = min_start + timedelta(days=flexibility)
        ideal_end = min_start + timedelta(days=ideal_offset)
        tags = {area, "Subway"} if random.random() < 0.1 else {area}
        jobs.append(
            Job(
                job_id=i,
                name=f"{area} {target}",
                duration_in_days=duration,
                min_start_date=min_start,
                max_end_date=max_end,
                ideal_end_date=ideal_end,
                tags=tuple(sorted(tags)),
            )
        )
    result = MaintenanceSchedule(calendar, crews, jobs)
    result.validate()
    return result
