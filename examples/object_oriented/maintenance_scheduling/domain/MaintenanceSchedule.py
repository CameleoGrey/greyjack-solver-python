



class MaintenanceSchedule:

    def __init__(self, work_calendar=None, crews=None, jobs=None):

        self.work_calendar = work_calendar
        self.crews = crews
        self.jobs = jobs

        pass

    def print_schedule(self):
        
        for job in self.jobs:
            job_info = "Job id: {} | Name: {} | Duration {} | Must be done in {} - {} (ideally at {}) | Tags: {} | Crew {}: {} | Planned start: {}".format(
                job.job_id, job.name, job.duration_in_days, job.min_start_date, job.max_end_date, job.ideal_end_date, job.tags,
                job.crew_id, self.crews[job.crew_id].name, self.work_calendar.work_day_list[job.start_date_id]
            )
            print(job_info)
        
        pass