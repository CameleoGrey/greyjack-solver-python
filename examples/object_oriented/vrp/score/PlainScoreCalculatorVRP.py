import numpy as np

from greyjack.score_calculation.score_calculators.PlainScoreCalculator import PlainScoreCalculator
from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
from numba import jit

class PlainScoreCalculatorVRP(PlainScoreCalculator):

    def __init__(self):
        super().__init__()

        self.score_variant = ScoreVariants.HardMediumSoftScore
        
        self.add_prescoring_function("build_common_df", self.build_common_df)

        self.add_constraint("no_duplicating_stops_constraint", self.no_duplicating_stops_constraint)
        self.add_constraint("capacity_constraint", self.capacity_constraint)
        self.add_constraint("late_arrival_penalty", self.late_arrival_penalty)
        self.add_constraint("minimize_distance", self.minimize_distance)

        pass

    def build_common_df(self, planning_entity_dfs, problem_fact_dfs):

        customers_df = problem_fact_dfs["customers"]
        vehicle_df = problem_fact_dfs["vehicles"]
        planning_stops_df = planning_entity_dfs["planning_stops"]

        customers_df = customers_df.rename({"customer_vec_id": "customer_id"})
        common_df = (planning_stops_df
                      .with_row_index("index", offset=None)
                      .join(vehicle_df, on="vehicle_id", how="inner")
                      .join(customers_df, on="customer_id", how="inner")
                      .sort(["sample_id", "vehicle_id", "index"], descending=[False, False, False]))

        self.utility_objects["common_df"] = common_df
        
        pass

    def no_duplicating_stops_constraint(self, planning_entity_dfs, problem_fact_dfs):

        path_stops_df = planning_entity_dfs["planning_stops"]

        duplicate_counts = (
            path_stops_df
            .group_by("sample_id")
            .agg((pl.col("customer_id").count() - pl.col("customer_id").n_unique()).alias("duplicates_count"))
            .group_by("sample_id")
            .agg(pl.col("duplicates_count").sum())
            .sort("sample_id")
        )

        scores = duplicate_counts["duplicates_count"].to_numpy()
        scores = 1000 * scores # multiply for competing with capacity constraint
        scores = [HardMediumSoftScore(score, 0, 0) for score in scores]

        return scores

    def capacity_constraint(self, planning_entity_dfs, problem_fact_dfs):
        common_df = self.utility_objects["common_df"]
        vehicle_df = problem_fact_dfs["vehicles"]

        capacity_penalties = (
            common_df
            .group_by(["sample_id", "vehicle_id"])
            .agg(pl.col("demand").sum().alias("sum_trip_demand"))
            .join(vehicle_df, on="vehicle_id", how="inner")
            .with_columns((pl.col("capacity") - pl.col("sum_trip_demand")).alias("capacity_difference"))
            .filter(pl.col("capacity_difference") < 0)
            .group_by("sample_id")
            .agg(pl.col("capacity_difference").abs().sum().alias("capacity_constraint_penalty"))
        )

        bad_sample_ids = capacity_penalties["sample_id"].to_list()
        capacity_penalties = capacity_penalties["capacity_constraint_penalty"].to_list()
        samples_count = common_df["sample_id"].n_unique()

        scores = []
        for sample_id in range(samples_count):
            current_score = HardMediumSoftScore(0, 0, 0)
            scores.append(current_score)

        for i, bad_sample_id in enumerate(bad_sample_ids):
            scores[bad_sample_id].hard_score = capacity_penalties[i]

        return scores

    def late_arrival_penalty(self, planning_entity_dfs, problem_fact_dfs):

        common_df = self.utility_objects["common_df"]
        data_matrix = common_df[["sample_id", "vehicle_id", "work_day_start", "work_day_end",
                                 "time_window_start", "time_window_end", "service_time"]].to_numpy()
        time_penalties = self.compute_time_penalties(data_matrix)

        scores = []
        for time_penalty in time_penalties:
            current_score = HardMediumSoftScore(0.0, time_penalty, 0)
            scores.append(current_score)

        return scores

    @staticmethod
    @jit(nopython=True, cache=True)  # numba gives speed similar to Java, see: (https://github.com/jabbalaci/SpeedTests)
    def compute_time_penalties(data_matrix):

        unique_sample_ids = np.unique(data_matrix[:, 0])
        n_samples = unique_sample_ids.shape[0]
        sample_size = data_matrix.shape[0] // n_samples
        time_penalties = np.zeros((n_samples,), dtype=np.float32)

        # using some optimizations (avoiding filtering comparison in each loop) to make
        # score calculation time linear (look closely into loops structure) for the current population / candidates batch
        for sample_id in unique_sample_ids:
            # sample_matrix = data_matrix[data_matrix[:, 0] == sample_id]
            sample_matrix = data_matrix[sample_id * sample_size: (sample_id + 1) * sample_size]

            # unique_vehicle_ids = np.unique(sample_matrix[:, 1])
            # for vehicle_id in unique_vehicle_ids:
            # vehicle_matrix = sample_matrix[sample_matrix[:, 1] == vehicle_id]
            vehicle_vec_start = 0
            vehicle_vec_end = 0
            last_sample_vec_id = sample_matrix.shape[0] - 1
            current_vehicle_id = sample_matrix[vehicle_vec_start, 1]
            while vehicle_vec_start <= last_sample_vec_id:
                while sample_matrix[vehicle_vec_end, 1] == current_vehicle_id:
                    vehicle_vec_end += 1
                    if vehicle_vec_end > last_sample_vec_id:
                        break
                vehicle_matrix = sample_matrix[vehicle_vec_start: vehicle_vec_end]

                work_day_start = vehicle_matrix[0][2]
                work_day_end = vehicle_matrix[0][3]
                window_starts = vehicle_matrix[:, 4]
                window_ends = vehicle_matrix[:, 5]
                service_times = vehicle_matrix[:, 6]

                trip_time_penalty = 0
                current_arrival_time = work_day_start
                for i in range(0, len(window_starts)):
                    customer_window_start = window_starts[i]
                    customer_window_end = window_ends[i]
                    customer_service_time = service_times[i]

                    # if arrive too early - wait
                    current_arrival_time = max(current_arrival_time, customer_window_start)

                    if current_arrival_time > customer_window_end + customer_service_time:
                        trip_time_penalty += current_arrival_time - (customer_window_end + customer_service_time)

                    current_arrival_time += customer_service_time

                if current_arrival_time > work_day_end:
                    trip_time_penalty += current_arrival_time - work_day_end


                time_penalties[sample_id] += trip_time_penalty

                if vehicle_vec_end > last_sample_vec_id:
                    break
                vehicle_vec_start = vehicle_vec_end
                current_vehicle_id = sample_matrix[vehicle_vec_start, 1]

        return time_penalties


    def minimize_distance(self, planning_entity_dfs, problem_fact_dfs):

        common_df = self.utility_objects["common_df"]
        distance_matrix = self.utility_objects["distance_matrix"]
        data_matrix = common_df[["sample_id", "vehicle_id", "matrix_depot_id", "customer_id"]].to_numpy()
        path_distances = self.compute_path_distances(data_matrix, distance_matrix)

        scores = []
        for path_distance in path_distances:
            current_score = HardMediumSoftScore(0, 0, path_distance)
            scores.append(current_score)

        return scores

    @staticmethod
    @jit(nopython=True, cache=True) # numba gives speed similar to Java, see: (https://github.com/jabbalaci/SpeedTests)
    def compute_path_distances(data_matrix, distance_matrix):

        unique_sample_ids = np.unique(data_matrix[:, 0])
        n_samples = unique_sample_ids.shape[0]
        sample_size = data_matrix.shape[0] // n_samples
        path_distances = np.zeros((n_samples,), dtype=np.float32)

        # using some optimizations (avoiding filtering comparison in each loop) to make
        # score calculation time linear (look closely into loops structure) for the current population / candidates batch
        for sample_id in unique_sample_ids:
            #sample_matrix = data_matrix[data_matrix[:, 0] == sample_id]
            sample_matrix = data_matrix[sample_id * sample_size : (sample_id + 1) * sample_size]

            # unique_vehicle_ids = np.unique(sample_matrix[:, 1])
            # for vehicle_id in unique_vehicle_ids:
                # vehicle_matrix = sample_matrix[sample_matrix[:, 1] == vehicle_id]
            vehicle_vec_start = 0
            vehicle_vec_end = 0
            last_sample_vec_id = sample_matrix.shape[0] - 1
            current_vehicle_id = sample_matrix[vehicle_vec_start, 1]
            while vehicle_vec_start <= last_sample_vec_id:
                while sample_matrix[vehicle_vec_end, 1] == current_vehicle_id:
                    vehicle_vec_end += 1
                    if vehicle_vec_end > last_sample_vec_id:
                        break
                vehicle_matrix = sample_matrix[vehicle_vec_start : vehicle_vec_end]

                depot_vec_id = vehicle_matrix[0][2]
                planning_stop_ids = vehicle_matrix[:, 3]

                current_path_distance = 0
                current_path_distance += distance_matrix[depot_vec_id][planning_stop_ids[0]]
                current_path_distance += distance_matrix[planning_stop_ids[-1]][depot_vec_id]
                for i in range(1, len(planning_stop_ids)):
                    from_id = planning_stop_ids[i - 1]
                    to_id = planning_stop_ids[i]
                    current_path_distance += distance_matrix[from_id][to_id]

                path_distances[sample_id] += current_path_distance

                if vehicle_vec_end > last_sample_vec_id:
                    break
                vehicle_vec_start = vehicle_vec_end
                current_vehicle_id = sample_matrix[vehicle_vec_start, 1]

        return path_distances