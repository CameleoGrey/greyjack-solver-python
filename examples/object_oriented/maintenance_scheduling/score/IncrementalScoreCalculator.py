
from greyjack.score_calculation.score_calculators.IncrementalScoreCalculator import IncrementalScoreCalculator
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
import numpy as np
import numba
from numba import jit, int64, float64, vectorize


class IncrementalScoreCalculator(IncrementalScoreCalculator):
    def __init__(self):
        super().__init__()
        self.score_variant = ScoreVariants.HardSoftScore
        self.add_constraint("all_in_one_constraint", self.all_in_one_constraint)
        pass

    def all_in_one_constraint(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):

        # pseudo-incremental approach

        jobs_df = planning_entity_dfs["jobs"]
        jobs_delta_df = delta_dfs["jobs"]

        work_day_list = self.utility_objects["work_day_list"]
        durations_in_days = self.utility_objects["durations_in_days"]
        min_start_dates = self.utility_objects["min_start_dates"]
        max_end_dates = self.utility_objects["max_end_dates"]
        ideal_end_dates = self.utility_objects["ideal_end_dates"]
        tags = self.utility_objects["tags"]

        scores = []
        n_jobs = len(min_start_dates)
        native_crew_ids = jobs_df["crew_id"].to_numpy()
        native_start_date_ids = jobs_df["start_date_id"].to_numpy()
        for sample_df in jobs_delta_df.partition_by(["sample_id"], maintain_order=True, include_key=False):
            delta_row_ids = sample_df["candidate_df_row_id"].to_numpy()
            crew_delta_ids = sample_df["crew_id"].to_numpy()
            start_date_delta_ids = sample_df["start_date_id"].to_numpy()

            (crew_conflict_penalty, min_start_date_penalty, max_end_date_penalty,
             before_ideal_date_penalty, after_ideal_date_penalty, tag_conflict_penalty) = compute_penalties(
                 work_day_list, durations_in_days, min_start_dates, max_end_dates, ideal_end_dates, tags,
                 n_jobs, native_crew_ids, native_start_date_ids, delta_row_ids, crew_delta_ids, start_date_delta_ids)

            sample_score = HardSoftScore(
                crew_conflict_penalty + min_start_date_penalty + max_end_date_penalty,
                before_ideal_date_penalty + after_ideal_date_penalty + tag_conflict_penalty
            )

            scores.append(sample_score)

        return scores

@jit(nopython=True, cache=True)
def compute_penalties(
    work_day_list,
    durations_in_days,
    min_start_dates,
    max_end_dates,
    ideal_end_dates,
    tags,

    n_jobs,
    native_crew_ids,
    native_start_date_ids,
    delta_row_ids,
    crew_delta_ids,
    start_date_delta_ids,

):
    
    sample_crew_ids = native_crew_ids.copy()
    sample_crew_ids[delta_row_ids] = crew_delta_ids

    sample_start_date_ids = native_start_date_ids.copy()
    sample_start_date_ids[delta_row_ids] = start_date_delta_ids

    start_dates = np.zeros((n_jobs, ), np.int64)
    end_dates = np.zeros((n_jobs, ), np.int64)
    for i, start_day_id in enumerate(sample_start_date_ids):
        start_dates[i] = work_day_list[start_day_id]

        # duration in work days!
        end_date_id = start_day_id + durations_in_days[i]
        if end_date_id < len(work_day_list):
            # get correct date from calendar (theme with excluding holidays)
            end_dates[i] = work_day_list[end_date_id]
        else:
            # if date goes outside planning period (work calendar)
            # we still need some date to compute penalty later
            outside_delta_days = end_date_id - len(work_day_list) + 1
            end_dates[i] = work_day_list[-1] + outside_delta_days
    


    min_start_date_penalty = 0
    max_end_date_penalty = 0
    before_ideal_date_penalty = 0
    after_ideal_date_penalty = 0
    for i in range(n_jobs):

        if start_dates[i] < min_start_dates[i] and min_start_dates[i] != -1:
            min_start_date_penalty += 1 * (min_start_dates[i] - start_dates[i])

        if end_dates[i] > max_end_dates[i] and max_end_dates[i] != -1:
            max_end_date_penalty += 1 * (end_dates[i] - max_end_dates[i])
        
        if end_dates[i] < ideal_end_dates[i] and ideal_end_dates[i] != -1:
            before_ideal_date_penalty += 1
        
        if end_dates[i] > ideal_end_dates[i] and ideal_end_dates[i] != -1:
            after_ideal_date_penalty += 1_000_000


    crew_conflict_penalty = 0
    tag_conflict_penalty = 0
    for i in range(n_jobs):
        for j in range(n_jobs):

            crew_i = sample_crew_ids[i]
            crew_j = sample_crew_ids[j]

            if i == j:
                continue
            if crew_i != crew_j:
                continue
            
            # A crew can do at most one maintenance job at the same time.
            days_overlapping = min(end_dates[i], end_dates[j]) - max(start_dates[i], start_dates[j])
            if days_overlapping > 0:
                crew_conflict_penalty += days_overlapping
                #crew_conflict_penalty += 1
            
            # Avoid overlapping maintenance jobs with the same tag (for example road maintenance in the same area).
            tags_intersection_size = len(np.intersect1d(tags[i], tags[j], assume_unique=True))
            tag_conflict_penalty += 1_000 * tags_intersection_size * abs(days_overlapping)



    return (crew_conflict_penalty, min_start_date_penalty, max_end_date_penalty,
             before_ideal_date_penalty, after_ideal_date_penalty, tag_conflict_penalty)