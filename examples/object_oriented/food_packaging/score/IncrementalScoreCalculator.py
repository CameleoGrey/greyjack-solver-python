
from greyjack.score_calculation.score_calculators.IncrementalScoreCalculator import IncrementalScoreCalculator
from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
import numpy as np
import numba
from numba import jit, int64, float64, vectorize


class IncrementalScoreCalculator(IncrementalScoreCalculator):
    def __init__(self):
        super().__init__()
        self.score_variant = ScoreVariants.HardMediumSoftScore
        self.add_constraint("all_in_one_constraint", self.all_in_one_constraint)
        pass

    def all_in_one_constraint(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):

        product_ids = self.utility_objects["product_ids"]
        durations = self.utility_objects["durations"]
        min_start_times = self.utility_objects["min_start_times"]
        ideal_end_times = self.utility_objects["ideal_end_times"]
        max_end_times = self.utility_objects["max_end_times"]
        priorities = self.utility_objects["priorities"]
        operators = self.utility_objects["operators"]
        start_date_times = self.utility_objects["start_date_times"]
        m_lines = self.utility_objects["m_lines"]
        cleaning_duration_matrix = self.utility_objects["cleaning_duration_matrix"]

        jobs_df = planning_entity_dfs["jobs"]
        jobs_delta_df = delta_dfs["jobs"]

        job_ids = jobs_df["job_id"].to_numpy()
        native_line_ids = jobs_df["line_id"].to_numpy()
        native_line_positions = jobs_df["line_position"].to_numpy()

        scores = []
        for sample_df in jobs_delta_df.partition_by(["sample_id"], maintain_order=True, include_key=False):

            delta_row_ids = sample_df["candidate_df_row_id"].to_numpy()
            line_delta_ids = sample_df["line_id"].to_numpy()
            line_position_deltas = sample_df["line_position"].to_numpy()

            (unique_positions_penalty, too_late_penalty, unideal_end_time_penalty, 
            operator_cleaning_conflict_penalty, makespan_penalty, cleaning_duration_penalty) = compute_penalties(
                 product_ids, durations, min_start_times, ideal_end_times, max_end_times, priorities, operators, start_date_times, m_lines, cleaning_duration_matrix,
                 job_ids, native_line_ids, native_line_positions,
                 delta_row_ids, line_delta_ids, line_position_deltas)

            #Like in Timefold
            """sample_score = HardMediumSoftScore(
                unique_positions_penalty + too_late_penalty,
                unideal_end_time_penalty,
                operator_cleaning_conflict_penalty + makespan_penalty + cleaning_duration_penalty
            )"""
            
            # My variant. I don't understand, why ideal timing of a particular job's ending is more important than total jobs completion time.
            # From other side, such score structure solves problem of dwarfing non-squared penalties
            sample_score = HardMediumSoftScore(
                unique_positions_penalty + too_late_penalty,
                makespan_penalty,
                operator_cleaning_conflict_penalty + unideal_end_time_penalty + cleaning_duration_penalty
            )

            scores.append(sample_score)

        return scores
    

@jit(nopython=True, cache=True)
def compute_penalties(
    product_ids,
    durations,
    min_start_times,
    ideal_end_times,
    max_end_times,
    priorities,
    operators,
    start_date_times,
    m_lines,
    cleaning_duration_matrix,

    job_ids,
    native_line_ids,
    native_line_positions,

    delta_row_ids,
    line_delta_ids,
    line_position_deltas,
):
    
    sample_line_ids = native_line_ids.copy()
    sample_line_ids[delta_row_ids] = line_delta_ids
    sample_line_positions = native_line_positions.copy()
    sample_line_positions[delta_row_ids] = line_position_deltas

    n_jobs = job_ids.shape[0]
    MAX_INT = np.iinfo(np.int64).max

    line_jobs = np.zeros((m_lines, n_jobs), np.int64) + MAX_INT
    line_positions = np.zeros((m_lines, n_jobs), np.int64) + MAX_INT
    line_ids_counters = np.zeros((m_lines, ), np.int64)
    for i in range(len(job_ids)):
        line_id = sample_line_ids[i]
        line_jobs[line_id][line_ids_counters[line_id]] = job_ids[i]
        line_positions[line_id][line_ids_counters[line_id]] = sample_line_positions[i]
        line_ids_counters[line_id] += 1
    for i in range(m_lines):
        sorted_ids = np.argsort(line_positions[i])
        line_positions[i] = line_positions[i][sorted_ids]
        line_jobs[i] = line_jobs[i][sorted_ids]

    all_jobs_start_production_times = np.zeros((n_jobs, ), np.int64)
    all_jobs_start_cleaning_times = np.zeros((n_jobs, ), np.int64)
    all_jobs_operators = np.zeros((n_jobs, ), np.int64)

    unique_positions_penalty = 0
    too_late_penalty = 0
    unideal_end_time_penalty = 0
    makespan_penalty = 0
    cleaning_duration_penalty = 0
    for i in range(m_lines):
        current_penalty = line_positions[i][:line_ids_counters[i]].shape[0] - np.unique(line_positions[i][:line_ids_counters[i]]).shape[0]
        unique_positions_penalty += 100000 * current_penalty

        current_line_jobs = line_jobs[i][:line_ids_counters[i]]
        if current_line_jobs.shape[0] == 0:
            continue
        
        job_start_cleaning = np.zeros((current_line_jobs.shape[0], ), np.int64)
        job_end_cleaning = np.zeros((current_line_jobs.shape[0], ), np.int64)
        line_jobs_ids = np.zeros((current_line_jobs.shape[0], ), np.int64)
        job_start_production_times = np.zeros((current_line_jobs.shape[0], ), np.int64)
        job_end_times = np.zeros((current_line_jobs.shape[0], ), np.int64)
        job_ideal_times = np.zeros((current_line_jobs.shape[0], ), np.int64)
        job_max_end_times = np.zeros((current_line_jobs.shape[0], ), np.int64)
        line_product_ids = np.zeros((current_line_jobs.shape[0], ), np.int64)
        for j, job_id in enumerate(current_line_jobs):
            line_jobs_ids[j] = job_id
            all_jobs_operators[job_id] = operators[i]
            job_ideal_times[j] = ideal_end_times[job_id]
            job_max_end_times[j] = max_end_times[job_id]
            line_product_ids[j] = product_ids[job_id]

        job_start_production_times[0] += start_date_times[i]
        job_end_cleaning[0] += start_date_times[i] + durations[line_jobs_ids[0]] # nothing to clean yet
        all_jobs_start_cleaning_times[line_jobs_ids[0]] += job_end_cleaning[0]
        all_jobs_start_production_times[line_jobs_ids[0]] += job_start_production_times[0]
        for j in range(1, job_end_times.shape[0]):
            job_start_production_times[j] += job_end_cleaning[j-1]
            job_end_times[j] += job_start_production_times[j] + durations[line_jobs_ids[j]]
            job_start_cleaning[j] += job_end_times[j]
            current_cleaning_duration = cleaning_duration_matrix[line_product_ids[j]][line_product_ids[j-1]]
            job_end_cleaning[j] += job_start_cleaning[j] + current_cleaning_duration
            
            cleaning_duration_penalty += priorities[line_jobs_ids[j]] * current_cleaning_duration

            all_jobs_start_cleaning_times[line_jobs_ids[j]] = job_start_cleaning[j]
            all_jobs_start_production_times[line_jobs_ids[j]] = job_start_production_times[j]


        for j in range(job_end_times.shape[0]):
            if job_end_times[j] > job_max_end_times[j]:
                too_late_penalty += job_end_times[j] - job_max_end_times[j]
            if job_end_times[j] > job_ideal_times[j]:
                unideal_end_time_penalty += job_end_times[j] - job_ideal_times[j]

        makespan_penalty += np.square(job_end_times[-1] - start_date_times[i])
    
    operator_cleaning_conflict_penalty = 0
    for job_i in range(n_jobs):
        for job_j in range(n_jobs):

            if job_j >= job_i:
                continue
            if all_jobs_operators[job_i] != all_jobs_operators[job_j]:
                continue

            job_i_start_production_time = all_jobs_start_production_times[job_i]
            job_j_start_production_time = all_jobs_start_production_times[job_j]
            job_i_start_cleaning_time = all_jobs_start_cleaning_times[job_i]
            job_j_start_cleaning_time = all_jobs_start_cleaning_times[job_j]

            overlapping_minutes = min(job_i_start_cleaning_time, job_j_start_cleaning_time) - max(job_i_start_production_time, job_j_start_production_time)
            operator_cleaning_conflict_penalty += overlapping_minutes if overlapping_minutes > 0 else 0


    return (unique_positions_penalty, too_late_penalty, unideal_end_time_penalty, 
            operator_cleaning_conflict_penalty, makespan_penalty, cleaning_duration_penalty)