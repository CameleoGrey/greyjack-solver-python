
from greyjack.score_calculation.score_calculators.IncrementalScoreCalculator import IncrementalScoreCalculator
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
import numpy as np
import numba
from numba import jit, int64, float64, vectorize


class IncrementalScoreCalculatorNQueens(IncrementalScoreCalculator):
    def __init__(self):
        super().__init__()
        self.score_variant = ScoreVariants.SimpleScore
        self.add_constraint("all_different", self.all_different)
        pass

    def all_different(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):
        # pseudo-incremental manner: just use deltas to reduce planning dfs building cost
        # the score still computes on the whole vector sample
        # relatively easy implement and understand (comparable to true incremental or super optimized manner) 
        # with huge performance boost on large datasets

        queens_df = planning_entity_dfs["queens"]
        queens_deltas_df = delta_dfs["queens"]

        native_column_ids = queens_df["column_id"].to_numpy()
        native_row_ids = queens_df["row_id"].to_numpy()
        target_unique_row_ids_count = native_row_ids.shape[0]

        scores = []
        splitted_dfs = queens_deltas_df.partition_by(["sample_id"], maintain_order=True, include_key=False)
        for sample_df in splitted_dfs:
            delta_df_row_ids = sample_df["candidate_df_row_id"].to_numpy()
            delta_row_ids = sample_df["row_id"].to_numpy()
            sample_row_ids = native_row_ids.copy()

            sample_row_ids[delta_df_row_ids] = delta_row_ids

            unique_sample_row_ids = np.unique(sample_row_ids)
            unique_sample_desc_ids = np.unique(native_column_ids + sample_row_ids)
            unique_sample_asc_ids = np.unique(native_column_ids - sample_row_ids)

            unique_rows_penalty = target_unique_row_ids_count - unique_sample_row_ids.shape[0]
            unique_desc_ids_penalty = target_unique_row_ids_count - unique_sample_desc_ids.shape[0]
            unique_asc_ids_penalty = target_unique_row_ids_count - unique_sample_asc_ids.shape[0]

            total_penalty = unique_rows_penalty + unique_desc_ids_penalty + unique_asc_ids_penalty
            scores.append(SimpleScore(total_penalty))

        return scores
    
    """def all_different(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):
        # alternative (much more complex and faster) version
        # after experiments: better works on medium/low dimensions (especially with jit)

        queens_df = planning_entity_dfs["queens"]
        queens_deltas_df = delta_dfs["queens"]

        native_column_ids = queens_df["column_id"].to_numpy()
        native_row_ids = queens_df["row_id"].to_numpy()
        target_unique_row_ids_count = native_row_ids.shape[0]

        n_samples = queens_deltas_df["sample_id"].n_unique() # fast call to Rust function
        sample_array = queens_deltas_df.select(["sample_id", "candidate_df_row_id", "row_id"]).to_numpy() # guarantee of order
        scores = compute_score_values(
            native_column_ids, 
            native_row_ids, 
            target_unique_row_ids_count, 
            sample_array[:, 0],
            sample_array[:, 1], 
            sample_array[:, 2], 
            n_samples
            ) # jitted code
        scores = [SimpleScore(score_value) for score_value in scores]

        return scores"""
    
@staticmethod
@jit(nopython=True, cache=True)
#@numba.cfunc("float64[:](int64[:], int64[:], int64, int64[:], int64[:], int64[:], int64)")
def compute_score_values(
    native_column_ids, 
    native_row_ids, 
    target_unique_row_ids_count, 
    sample_ids,
    delta_df_row_ids,
    delta_row_ids,
    n_samples
    ):

    score_values = np.zeros((n_samples, ), dtype=np.float64)
    sample_array_id = 0
    batch_start = sample_array_id
    for sample_id in range(n_samples):
        sample_row_ids = native_row_ids.copy()

        while sample_ids[batch_start] == sample_ids[sample_array_id]:
            sample_row_ids[delta_df_row_ids[sample_array_id]] = delta_row_ids[sample_array_id]
            sample_array_id += 1
            if sample_array_id >= sample_ids.shape[0]:
                break
        batch_start = sample_array_id
        
        unique_sample_row_ids = np.unique(sample_row_ids)
        unique_sample_desc_ids = np.unique(native_column_ids + sample_row_ids)
        unique_sample_asc_ids = np.unique(native_column_ids - sample_row_ids)

        unique_rows_penalty = target_unique_row_ids_count - unique_sample_row_ids.shape[0]
        unique_desc_ids_penalty = target_unique_row_ids_count - unique_sample_desc_ids.shape[0]
        unique_asc_ids_penalty = target_unique_row_ids_count - unique_sample_asc_ids.shape[0]

        score_values[sample_id] = unique_rows_penalty + unique_desc_ids_penalty + unique_asc_ids_penalty

    return score_values
