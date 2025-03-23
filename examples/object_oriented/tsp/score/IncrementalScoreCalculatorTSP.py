
from greyjack.score_calculation.score_calculators.IncrementalScoreCalculator import IncrementalScoreCalculator
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
import numpy as np
import numba
from numba import jit, njit, int64, float64, vectorize
from functools import reduce


class IncrementalScoreCalculatorTSP(IncrementalScoreCalculator):
    def __init__(self):
        super().__init__()
        self.score_variant = ScoreVariants.HardSoftScore
        self.add_constraint("all_in_one_constraint", self.all_in_one_constraint)
        pass
    
    def all_in_one_constraint(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):
        # pseudo-incremental manner: just use deltas to reduce planning dfs building cost
        # the score still computes on the whole vector sample
        # relatively easy implement and understand (comparable to true incremental or super optimized manner) 
        # with huge performance boost on large datasets

        # from experiments: common performance up to ~2 times lower (depends on dataset size)
        # than in fully Rust version of SolverOOP. Need to keep in mind the opportunity of
        # rewriting constraints on Rust in Python version for production (if it's neccessary). 
        
        path_stops_df = planning_entity_dfs["path_stops"]
        path_stops_deltas_df = delta_dfs["path_stops"]
        distance_matrix = self.utility_objects["distance_matrix"]
        planning_stop_ids = path_stops_df["location_list_id"].to_numpy()
        last_id = planning_stop_ids.shape[0] - 1
        target_stops_count = planning_stop_ids.shape[0]
        
        scores = []
        for sample_df in path_stops_deltas_df.partition_by(["sample_id"], maintain_order=True, include_key=False):
            current_df_row_ids = sample_df["candidate_df_row_id"].to_numpy()
            current_loc_ids = sample_df["location_list_id"].to_numpy()          
            changed_stops = planning_stop_ids.copy()

            changed_stops[current_df_row_ids] = current_loc_ids
            
            # no_duplicating_stops_constraint
            unique_stops_penalty = target_stops_count - np.unique(changed_stops).shape[0]
            
            # minimizing distance
            sample_distance = distance_matrix[0][changed_stops[0]] + \
                              np.sum(distance_matrix[changed_stops[i-1]][changed_stops[i]] for i in range(1, len(changed_stops))) + \
                              distance_matrix[changed_stops[last_id]][0]
            #reduce(lambda i: distance_matrix[changed_stops[i-1]][changed_stops[i]], range(1, len(changed_stops)))

            # same speed
            #penalties = compute_penalties(changed_stops, current_df_row_ids, current_loc_ids, distance_matrix, last_id, target_stops_count)
            #unique_stops_penalty, sample_distance = penalties[0], penalties[1]

            scores.append(HardSoftScore(unique_stops_penalty, sample_distance))
        
        return scores

@staticmethod
@jit(nopython=True, cache=True)
def compute_penalties(changed_stops, current_df_row_ids, current_loc_ids, distance_matrix, last_id, target_stops_count):
    changed_stops[current_df_row_ids] = current_loc_ids
        
    # no_duplicating_stops_constraint
    unique_stops_penalty = target_stops_count - np.unique(changed_stops).shape[0]
    
    # minimizing distance
    sample_distance = distance_matrix[0][changed_stops[0]] + \
                        np.sum(distance_matrix[changed_stops[i-1]][changed_stops[i]] for i in range(1, len(changed_stops))) + \
                        distance_matrix[changed_stops[last_id]][0]
    
    penalties = np.zeros((2, ), dtype=np.float64)
    penalties[0] = unique_stops_penalty
    penalties[1] = sample_distance

    return penalties

        
