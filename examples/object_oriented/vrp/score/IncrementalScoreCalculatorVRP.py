
from greyjack.score_calculation.score_calculators.IncrementalScoreCalculator import IncrementalScoreCalculator
from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
import numpy as np
import numba
from numba import jit, int64, float64, vectorize
from functools import reduce


class IncrementalScoreCalculatorVRP(IncrementalScoreCalculator):
    def __init__(self):
        super().__init__()
        self.score_variant = ScoreVariants.HardMediumSoftScore
        self.add_constraint("all_in_one_constraint", self.all_in_one_constraint)
        pass

    def all_in_one_constraint(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):
        # pseudo-incremental manner: just use deltas to reduce planning dfs building cost
        # the score still computes on the whole vector sample
        # relatively easy implement and understand (comparable to true incremental or super optimized manner) 
        # with huge performance boost on large datasets

        # from experiments: shows ~70% of clean Rust version performance (in average)
        
        planning_stops_df = planning_entity_dfs["planning_stops"]
        path_stops_deltas_df = delta_dfs["planning_stops"]
        distance_matrix = self.utility_objects["distance_matrix"]
        
        # to avoid joining
        capacities = self.utility_objects["vehicle_capacities"]
        depot_ids = self.utility_objects["depot_ids"]
        demands = self.utility_objects["demands"]
        is_time_windowed = self.utility_objects["time_windowed"]
        if is_time_windowed:
            work_day_starts = self.utility_objects["work_day_starts"]
            work_day_ends = self.utility_objects["work_day_ends"]
            time_window_starts = self.utility_objects["time_window_starts"]
            time_window_ends = self.utility_objects["time_window_ends"]
            service_times = self.utility_objects["service_times"]
        else:
            # to not catch error in the not time_windowed scenario
            work_day_starts = np.zeros((1,), dtype=np.int64)
            work_day_ends = np.zeros((1,), dtype=np.int64)
            time_window_starts = np.zeros((1,), dtype=np.int64)
            time_window_ends = np.zeros((1,), dtype=np.int64)
            service_times = np.zeros((1,), dtype=np.int64)
        
        k_vehicles = len(capacities)
        vehicle_null_penalties = np.zeros((k_vehicles,), dtype=np.float64)
        null_trip_demands = np.zeros((k_vehicles,), dtype=np.float64)
        
        native_vehicle_ids = planning_stops_df["vehicle_id"].to_numpy()
        native_customer_ids = planning_stops_df["customer_id"].to_numpy()
        n_customers = len(planning_stops_df["customer_id"])
        
        scores = []
        for sample_df in path_stops_deltas_df.partition_by(["sample_id"], maintain_order=True, include_key=False):
            delta_row_ids = sample_df["candidate_df_row_id"].to_numpy()
            vehicle_delta_ids = sample_df["vehicle_id"].to_numpy()
            customer_delta_ids = sample_df["customer_id"].to_numpy()
            
            sample_vehicle_ids = native_vehicle_ids.copy()
            sample_customer_ids = native_customer_ids.copy()
            sum_trip_demands = null_trip_demands.copy()

            penalties = compute_penalties(sample_vehicle_ids, sample_customer_ids, delta_row_ids, vehicle_delta_ids, customer_delta_ids,
                                          n_customers, sum_trip_demands, demands, capacities, k_vehicles, vehicle_null_penalties,
                                          distance_matrix, depot_ids, is_time_windowed, work_day_starts, work_day_ends, time_window_starts,
                                          time_window_ends, service_times)
            unique_stops_penalty, capacity_penalty, sum_time_penalty, sum_distance = penalties[0], penalties[1], penalties[2], penalties[3]
            
            scores.append(HardMediumSoftScore(unique_stops_penalty + capacity_penalty, sum_time_penalty, sum_distance))
        
        return scores

@staticmethod
@jit(nopython=True, cache=True)
def compute_penalties(
    sample_vehicle_ids,
    sample_customer_ids,
    delta_row_ids,
    vehicle_delta_ids,
    customer_delta_ids,
    n_customers,
    sum_trip_demands,
    demands,
    capacities,
    k_vehicles,
    vehicle_null_penalties,
    distance_matrix,
    depot_ids,
    is_time_windowed,
    work_day_starts,
    work_day_ends,
    time_window_starts,
    time_window_ends,
    service_times
):
    sample_vehicle_ids[delta_row_ids] = vehicle_delta_ids
    sample_customer_ids[delta_row_ids] = customer_delta_ids
    
    # no_duplicating_stops_constraint
    unique_stops_penalty = 1000.0 * (n_customers - len(np.unique(sample_customer_ids)))
    
    # capacity_constraint
    for v_id, c_id in zip(sample_vehicle_ids, sample_customer_ids):
        sum_trip_demands[v_id] += demands[c_id]
    
    capacity_differences = [capacities[v_id] - sum_trip_demands[v_id] for v_id in range(k_vehicles)]
    capacity_penalties = np.zeros((len(capacity_differences)), dtype=np.int64)
    for i in range(len(capacity_penalties)):
        if capacity_differences[i] < 0:
            capacity_penalties[i] = np.abs(capacity_differences[i])
    capacity_penalty = np.sum(capacity_penalties)
    
    #######################################################################
    vehicle_stops = np.zeros((k_vehicles, n_customers), np.int64)
    stops_counts = np.zeros(k_vehicles, dtype=np.int64)
    for v_id, c_id in zip(sample_vehicle_ids, sample_customer_ids):
        vehicle_stops[v_id][stops_counts[v_id]] = c_id
        stops_counts[v_id] += 1
    
    vehicle_distances = vehicle_null_penalties.copy()
    vehicle_time_penalties = vehicle_null_penalties.copy()
    
    for v_id in range(k_vehicles):
        if stops_counts[v_id] > 0:
            # minimize_distance
            last_id = stops_counts[v_id] - 1
            vehicle_distances[v_id] += distance_matrix[depot_ids[v_id]][vehicle_stops[v_id][0]]
            vehicle_distances[v_id] += distance_matrix[vehicle_stops[v_id][last_id]][depot_ids[v_id]]
            for i in range(1, last_id + 1):
                vehicle_distances[v_id] += distance_matrix[vehicle_stops[v_id][i-1]][vehicle_stops[v_id][i]]
            
            if is_time_windowed:
                # late_arrival_penalty
                work_day_start = work_day_starts[v_id]
                work_day_end = work_day_ends[v_id]
                current_arrival_time = work_day_start
                
                for i in range(stops_counts[v_id]):
                    customer_i_start = time_window_starts[vehicle_stops[v_id][i]]
                    customer_i_end = time_window_ends[vehicle_stops[v_id][i]]
                    customer_i_service_time = service_times[vehicle_stops[v_id][i]]
                    
                    current_arrival_time = max(current_arrival_time, customer_i_start)
                    if current_arrival_time + customer_i_service_time > customer_i_end:
                        vehicle_time_penalties[v_id] += (current_arrival_time + customer_i_service_time - customer_i_end)
                    
                    current_arrival_time += customer_i_service_time
                
                if current_arrival_time > work_day_end:
                    vehicle_time_penalties[v_id] += (current_arrival_time - work_day_end)
    
    sum_distance = np.sum(vehicle_distances)
    sum_time_penalty = np.sum(vehicle_time_penalties)

    penalties = np.zeros((4, ), dtype=np.float64)
    penalties[0] = unique_stops_penalty
    penalties[1] = capacity_penalty
    penalties[2] = sum_time_penalty
    penalties[3] = sum_distance

    return penalties

