

import numpy as np
from datetime import datetime
from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger
from examples.object_oriented.maintenance_scheduling.cotwin.Cotwin import Cotwin
from examples.object_oriented.maintenance_scheduling.cotwin.CotJob import CotJob
from examples.object_oriented.maintenance_scheduling.score.IncrementalScoreCalculator import IncrementalScoreCalculator
from examples.object_oriented.maintenance_scheduling.score.PlainScoreCalculator import PlainScoreCalculator


class CotwinBuilder(CotwinBuilderBase):
    def __init__(self, use_incremental_score_calculator, use_greed_init):
        self.use_incremental_score_calculator = use_incremental_score_calculator
        self.use_greed_init = use_greed_init
        pass

    def build_cotwin(self, domain, is_already_initialized):

        cotwin = Cotwin()

        planning_jobs = self._build_planning_jobs(domain, is_already_initialized)

        if self.use_incremental_score_calculator:
            score_calculator = IncrementalScoreCalculator()
            self._add_utility_info_for_incremental_scoring(domain, score_calculator, planning_jobs)
            # keep only changing fields and ids to improve df building speed (we will use utility objects to get constant info)
            self._remove_redundant_fields(planning_jobs, ["name", "duration_in_days", "min_start_date", "max_end_date", "ideal_end_date", "tags"])
        else:
            score_calculator = PlainScoreCalculator()

        cotwin.add_planning_entities_list(planning_jobs, "jobs")

        cotwin.set_score_calculator( score_calculator )

        return cotwin
    
    def _add_utility_info_for_incremental_scoring(self, domain, score_calculator, planning_jobs):

        encoded_work_days = []
        for work_day in domain.work_calendar.work_day_list:
            work_day = int(datetime.combine(work_day, datetime.min.time()).timestamp() // (24*60*60))
            encoded_work_days.append(work_day)
        score_calculator.utility_objects["work_day_list"] = np.array(encoded_work_days, np.int64)

        all_tags = set()
        for planning_job in planning_jobs:
            for tag_name in planning_job.tags:
                all_tags.add(tag_name)
        all_tags = list(sorted(list(all_tags)))
        tag_to_int_map = {k: v for v, k in enumerate(all_tags)}

        # Warning! Suggesting, that job ids are in range(0, n_jobs)
        durations_in_days = []
        min_start_dates = []
        max_end_dates = []
        ideal_end_dates = []
        tags = []
        for planning_job in planning_jobs:
            durations_in_days.append( planning_job.duration_in_days )

            if planning_job.min_start_date is None:
                min_start_dates.append(-1)
            else:
                min_start_dates.append( int(datetime.combine(planning_job.min_start_date, datetime.min.time()).timestamp() // (24*60*60)) )

            if planning_job.max_end_date is None:
                max_end_dates.append(-1)
            else:
                max_end_dates.append( int(datetime.combine(planning_job.max_end_date, datetime.min.time()).timestamp() // (24*60*60)) )

            if planning_job.ideal_end_date is None:
                ideal_end_dates.append(-1)
            else:
                ideal_end_dates.append( int(datetime.combine(planning_job.ideal_end_date, datetime.min.time()).timestamp() // (24*60*60)) )

            tags.append( np.array([tag_to_int_map[tag_name] for tag_name in planning_job.tags], np.int64) )
        score_calculator.utility_objects["durations_in_days"] = np.array(durations_in_days, np.int64)
        score_calculator.utility_objects["min_start_dates"] = np.array(min_start_dates, np.int64)
        score_calculator.utility_objects["max_end_dates"] = np.array(max_end_dates, np.int64)
        score_calculator.utility_objects["ideal_end_dates"] = np.array(ideal_end_dates, np.int64)
        score_calculator.utility_objects["tags"] = tags

        pass

    def _remove_redundant_fields(self, entities_list, redundant_fields):

        for i in range(len(entities_list)):
            for field_name in redundant_fields:
                delattr(entities_list[i], field_name)
    
    def _build_planning_jobs(self, domain, is_already_initialized):

        if is_already_initialized:
            raise Exception("Use of existing domain object is not already implemented for this task")
        
        if self.use_greed_init:
            raise Exception("greed init is not already implemented for this task")
        
        planning_jobs = []
        for domain_job in domain.jobs:
            planning_job = CotJob(
                job_id=domain_job.job_id, 
                name=domain_job.name, 
                duration_in_days=domain_job.duration_in_days,
                min_start_date=domain_job.min_start_date,
                max_end_date=domain_job.max_end_date, 
                ideal_end_date=domain_job.ideal_end_date, 
                tags=domain_job.tags, 
                crew_id=GJInteger(0, len(domain.crews)-1, False, None, semantic_groups=["crews"]),
                start_date_id=GJInteger(0, len(domain.work_calendar.work_day_list)-1, False, None, semantic_groups=["work_days"])
            )

            planning_jobs.append(planning_job)

        return planning_jobs



