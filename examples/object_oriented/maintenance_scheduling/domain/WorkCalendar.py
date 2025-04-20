
from datetime import date, datetime, timedelta



class WorkCalendar:

    def __init__(self, id=None, from_date=None, to_date=None):

        self.id = id
        self.from_date = from_date # inclusive
        self.to_date = to_date # exclusive
        self.work_day_list = self._build_work_day_list()

        pass

    def _build_work_day_list(self):

        work_day_list = []
        current_date = self.from_date
        while current_date < self.to_date:
            current_date = current_date + timedelta(days=1)
            # in [saturday, sunday]
            if current_date.weekday() in [5, 6]:
                continue

            work_day_list.append(current_date)
        
        return work_day_list
