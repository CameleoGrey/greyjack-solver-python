
from greyjack.score_calculation.score_calculators.IncrementalScoreCalculator import IncrementalScoreCalculator
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
import numpy as np
import numba
from numba import jit


class IncrementalScoreCalculatorCB(IncrementalScoreCalculator):
    def __init__(self):
        super().__init__()
        self.score_variant = ScoreVariants.HardSoftScore
        self.add_constraint("all_in_one_constraint", self.all_in_one_constraint)

        pass


    def all_in_one_constraint(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):

        # pseudo-incremental approach
        native_computer_ids = planning_entity_dfs["processes"]["computer_id"].to_numpy()
        processes_deltas_df = delta_dfs["processes"]
        processes_info = self.utility_objects["processes_info"]
        computers_info = self.utility_objects["computers_info"]
        computers_costs = self.utility_objects["computers_costs"]

        scores = []
        for sample_df in processes_deltas_df.partition_by(["sample_id"], maintain_order=True, include_key=False):
            delta_row_ids = sample_df["candidate_df_row_id"].to_numpy()
            computer_delta_ids = sample_df["computer_id"].to_numpy()
            resources_unacceptance, candidate_total_cost = compute_penalties(native_computer_ids, delta_row_ids, computer_delta_ids,
                                                                             computers_costs, computers_info, processes_info)
            scores.append(HardSoftScore(resources_unacceptance, candidate_total_cost))

        return scores
    
@staticmethod
@jit(nopython=True, cache=True)
def compute_penalties(
    native_computer_ids,
    delta_row_ids,
    computer_delta_ids,
    computers_costs,
    computers_info,
    processes_info,
):
    sample_computer_ids = native_computer_ids.copy()
    sample_computer_ids[delta_row_ids] = computer_delta_ids

    # soft score, current assigning costs
    candidate_total_cost = 0
    unique_computer_ids = np.unique(sample_computer_ids)
    for computer_id in unique_computer_ids:
        candidate_total_cost += computers_costs[computer_id]
    
    # hard score, unacceptable resources allocation
    consumed_resources = np.zeros((computers_info.shape[0], 3), dtype=np.int64)
    for process_id, computer_id in enumerate(sample_computer_ids):
        consumed_resources[computer_id] += processes_info[process_id]
    resource_deltas = consumed_resources - computers_info
    
    resource_deltas = np.where(resource_deltas > 0, resource_deltas, 0)
    resources_unacceptance = np.sum(resource_deltas)

    return resources_unacceptance, candidate_total_cost