



class CotJob:
    def __init__(self, job_id=None, name=None, duration_in_days=None, min_start_date=None,
                 max_end_date=None, ideal_end_date=None, tags=None, crew_id=None, start_date_id=None):
        self.job_id = job_id
        self.name = name
        self.duration_in_days = duration_in_days
        self.min_start_date = min_start_date
        self.max_end_date = max_end_date
        self.ideal_end_date = ideal_end_date

        self.tags = tags

        self.crew_id = crew_id
        self.start_date_id = start_date_id # assigned work_day_list id