
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

        shifts_df = planning_entity_dfs["shifts"]
        shifts_delta_df = delta_dfs["shifts"]

        shift_starts = self.utility_objects["shift_starts"]
        shift_ends = self.utility_objects["shift_ends"]
        shift_start_dates = self.utility_objects["shift_start_dates"]
        shift_req_skills = self.utility_objects["shift_req_skills"]

        employee_skills = self.utility_objects["employee_skills"]
        employee_unavailable_dates = self.utility_objects["employee_unavailable_dates"]
        employee_undesired_dates = self.utility_objects["employee_undesired_dates"]
        employee_desired_dates = self.utility_objects["employee_desired_dates"]

        scores = []
        n_shifts = len(shift_starts)
        native_employee_ids = shifts_df["employee_id"].to_numpy()
        for sample_df in shifts_delta_df.partition_by(["sample_id"], maintain_order=True, include_key=False):
            delta_row_ids = sample_df["candidate_df_row_id"].to_numpy()
            employee_delta_ids = sample_df["employee_id"].to_numpy()

            (skill_penalty, unavailable_penalty, overlapping_penalty, 
             unrelax_penalty, many_shifts_per_day_penalty,
             undesired_date_penalty, desired_date_reward, unfairness_penalty) = compute_penalties(
                 shift_starts, shift_ends, shift_start_dates, shift_req_skills, employee_skills,
                 employee_unavailable_dates, employee_undesired_dates, employee_desired_dates,
                 n_shifts, native_employee_ids, delta_row_ids, employee_delta_ids)

            sample_score = HardSoftScore(
                skill_penalty + unavailable_penalty + overlapping_penalty + unrelax_penalty + many_shifts_per_day_penalty,
                undesired_date_penalty + desired_date_reward + unfairness_penalty
            )

            scores.append(sample_score)

        return scores

@jit(nopython=True, cache=True)
def compute_penalties(
    shift_starts,
    shift_ends,
    shift_start_dates,
    shift_req_skills,
    employee_skills,
    employee_unavailable_dates,
    employee_undesired_dates,
    employee_desired_dates,

    n_shifts,
    native_employee_ids,
    delta_row_ids,
    employee_delta_ids,
):
    
    sample_employee_ids = native_employee_ids.copy()
    sample_employee_ids[delta_row_ids] = employee_delta_ids

    skill_penalty = 0 # required skill
    unavailable_penalty = 0 # unavailable employee
    undesired_date_penalty = 0 # uncomfort day to work
    desired_date_reward = 0 # preferable day to work
    for i in range(n_shifts):
        employee_id = sample_employee_ids[i]
        current_skills = employee_skills[employee_id]
        if shift_req_skills[i] not in current_skills:
            skill_penalty += 1
        
        current_unavailable_dates = employee_unavailable_dates[employee_id]
        current_undesired_dates = employee_undesired_dates[employee_id]
        current_desired_dates = employee_desired_dates[employee_id]
        if shift_start_dates[i] in current_unavailable_dates:
            unavailable_penalty += 1
        if shift_start_dates[i] in current_undesired_dates:
            undesired_date_penalty += 1
        if shift_start_dates[i] in current_desired_dates:
            desired_date_reward -= 1
    
    overlapping_penalty = 0 # no overlapping shifts
    unrelax_penalty = 0 # at least 10 hours between two shifts
    many_shifts_per_day_penalty = 0 # one shift per day
    for i in range(n_shifts):
        for j in range(n_shifts):

            employee_i = sample_employee_ids[i]
            employee_j = sample_employee_ids[j]

            if i == j:
                continue
            if employee_i != employee_j:
                continue

            shifts_overlapping = min(shift_ends[i], shift_ends[j]) - max(shift_starts[i], shift_starts[j])
            if shifts_overlapping > 0:
                overlapping_penalty += shifts_overlapping
            else:
                relax_duration = abs(shifts_overlapping)
                if relax_duration < 10 * 60:
                    unrelax_penalty += 10 * 60 - relax_duration
            
            if shift_start_dates[i] == shift_start_dates[j]:
                many_shifts_per_day_penalty += 1
    
    # load balancing
    # careful, assuming that employee ids are in range(0, m_employees)
    unfairness_penalty = 0
    m_employees = len(employee_skills)
    shifts_counts = np.zeros((m_employees,), np.int64)
    for i in range(n_shifts):
        shifts_counts[sample_employee_ids[i]] += 1
    unfairness_penalty += np.sqrt(np.sum(np.square(shifts_counts - shifts_counts.mean())))


    return (skill_penalty, unavailable_penalty, overlapping_penalty, unrelax_penalty, many_shifts_per_day_penalty,
                undesired_date_penalty, desired_date_reward, unfairness_penalty)