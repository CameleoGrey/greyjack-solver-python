
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

        consumers_df = planning_entity_dfs["consumers"]
        consumers_delta_df = delta_dfs["consumers"]

        distance_matrix = self.utility_objects["distance_matrix"]
        demands = self.utility_objects["demands"]
        location_ids = self.utility_objects["location_ids"]
        setup_costs = self.utility_objects["setup_costs"]
        capacities = self.utility_objects["capacities"]

        scores = []
        native_facility_ids = consumers_df["facility_id"].to_numpy()
        for sample_df in consumers_delta_df.partition_by(["sample_id"], maintain_order=True, include_key=False):
            delta_row_ids = sample_df["candidate_df_row_id"].to_numpy()
            facility_delta_ids = sample_df["facility_id"].to_numpy()

            (sum_setup_cost_penalty, distance_from_facility_penalty, capacity_penalty) = compute_penalties(
                distance_matrix, demands, location_ids, setup_costs, capacities,
                native_facility_ids, delta_row_ids, facility_delta_ids)

            sample_score = HardSoftScore(
                capacity_penalty,
                sum_setup_cost_penalty + distance_from_facility_penalty
            )

            scores.append(sample_score)

        return scores

@jit(nopython=True, cache=True)
def compute_penalties(
    distance_matrix,
    demands,
    location_ids,

    setup_costs,
    capacities,

    native_facility_ids,
    delta_row_ids,
    facility_delta_ids,
):  
    sample_facility_ids = native_facility_ids.copy()
    sample_facility_ids[delta_row_ids] = facility_delta_ids

    sum_setup_cost_penalty = 0
    used_facility_ids = np.unique(sample_facility_ids)
    for used_facility_id in used_facility_ids:
        sum_setup_cost_penalty += 2 * setup_costs[used_facility_id]

    n_facilities = setup_costs.shape[0]
    n_locations = distance_matrix.shape[0]
    n_consumers = n_locations - n_facilities

    distance_from_facility_penalty = 0
    sum_demands = np.zeros((n_facilities), np.int64)
    for i in range(n_consumers):
        consumer_id = n_facilities + i
        assigned_facility_id = sample_facility_ids[i]
        sum_demands[assigned_facility_id] += demands[consumer_id]

        consumer_location_id = location_ids[consumer_id]
        distance_from_facility_penalty += 5 * distance_matrix[consumer_location_id][assigned_facility_id]
    
    capacity_penalty = 0
    for i in range(n_facilities):
        capacity_delta = capacities[i] - sum_demands[i]
        if capacity_delta < 0:
            capacity_penalty += abs(capacity_delta)


    return (sum_setup_cost_penalty, distance_from_facility_penalty, capacity_penalty)