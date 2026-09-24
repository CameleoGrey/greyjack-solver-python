from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class WorkCalendar:
    id: int
    from_date: date
    to_date: date
    work_day_list: list[date] = field(init=False)

    def __post_init__(self) -> None:
        for label, value in (("from_date", self.from_date), ("to_date", self.to_date)):
            if not isinstance(value, date) or isinstance(value, datetime):
                raise ValueError(f"{label} must be a date-only value")
        if self.from_date >= self.to_date:
            raise ValueError("Calendar end must follow its start")
        self.work_day_list = self._build_work_day_list()

    def _build_work_day_list(self) -> list[date]:
        # Preserve the source's increment-before-check behavior. For a Monday
        # start, the first workday is Tuesday and the final one is the next Monday.
        workdays = []
        current = self.from_date
        while current < self.to_date:
            current += timedelta(days=1)
            if current.weekday() < 5:
                workdays.append(current)
        return workdays

    def end_date(self, start_date_id: int, duration_in_days: int) -> date:
        """Replay the source's workday-index and beyond-calendar end rule."""
        if not 0 <= start_date_id < len(self.work_day_list):
            raise ValueError("Start workday index is outside the calendar")
        if type(duration_in_days) is not int or duration_in_days < 1:
            raise ValueError("Job duration must be a positive integer")
        end_index = start_date_id + duration_in_days
        if end_index < len(self.work_day_list):
            return self.work_day_list[end_index]
        outside_delta_days = end_index - len(self.work_day_list) + 1
        return self.work_day_list[-1] + timedelta(days=outside_delta_days)
