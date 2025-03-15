import numpy as np

from greyjack.score_calculation.score_calculators.PlainScoreCalculator import PlainScoreCalculator
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
from numba import jit

class TSPPlainScoreCalculator( PlainScoreCalculator ):

    def __init__(self):
        super().__init__()

        self.add_constraint("no_duplicating_stops_constraint", self.no_duplicating_stops_constraint)
        self.add_constraint("minimize_distance", self.minimize_distance)

        self.score_variant = ScoreVariants.HardSoftScore

        pass


    def no_duplicating_stops_constraint(self, planning_entity_dfs, problem_fact_dfs):

        path_stops_df = planning_entity_dfs["path_stops"]

        #print(path_stops_df)

        duplicate_counts = (
            path_stops_df
            .group_by("sample_id")
            .agg((pl.col("location_list_id").count() - pl.col("location_list_id").n_unique()).alias("duplicates_count"))
            .group_by("sample_id")
            .agg(pl.col("duplicates_count").sum())
            .sort("sample_id")

        )

        scores = duplicate_counts["duplicates_count"].to_list()
        scores = [HardSoftScore(score, 0) for score in scores]

        return scores
    
    #########################################################################################
    # straitforward and fast (almost similar to clean Rust speed)
    """def minimize_distance(self, planning_entity_dfs, problem_fact_dfs):

        path_stops_df = planning_entity_dfs["path_stops"]
        distance_matrix = self.utility_objects["distance_matrix"]

        sample_dfs = path_stops_df.partition_by("sample_id")
        path_distances = []
        for sample_df in sample_dfs:
            planning_stop_ids = sample_df["location_list_id"].to_numpy()
            path_distance = self.compute_path_distance(planning_stop_ids, distance_matrix)
            path_distances.append( path_distance )

        scores = []
        for path_distance in path_distances:
            current_score = HardSoftScore(0, path_distance)
            scores.append(current_score)

        return scores

    # numba gives speed similar to Java, see: (https://github.com/jabbalaci/SpeedTests)
    # and helps to exclude python between numpy objects and functions calls (gives almost direct calls of numpy C code)
    # numba is perfect for writing small pieces of code (that difficult or imposible to express in Polars) with numpy objects
    # instead rewriting on Rust (to not increase complexity of project and still take huge performance boost)
    @staticmethod
    @jit(nopython=True)
    def compute_path_distance(planning_stop_ids, distance_matrix):
        current_path_distance = 0
        current_path_distance += distance_matrix[0][planning_stop_ids[0]]
        current_path_distance += distance_matrix[planning_stop_ids[-1]][0]
        for i in range(1, len(planning_stop_ids)):
            from_id = planning_stop_ids[i - 1]
            to_id = planning_stop_ids[i]
            current_path_distance += distance_matrix[from_id][to_id]

        return current_path_distance"""
    
    #################################################################################
    # slightly faster (~15%) than above variant, but more complex
    def minimize_distance(self, planning_entity_dfs, problem_fact_dfs):

        path_stops_df = planning_entity_dfs["path_stops"]
        distance_matrix = self.utility_objects["distance_matrix"]
        data_matrix = path_stops_df[["sample_id", "location_list_id"]].to_numpy()
        path_distances = self.compute_path_distances(data_matrix, distance_matrix)

        scores = []
        for path_distance in path_distances:
            current_score = HardSoftScore(0, path_distance)
            scores.append(current_score)

        return scores

    # numba gives speed similar to Java, see: (https://github.com/jabbalaci/SpeedTests)
    # and helps to exclude python between numpy objects and functions calls (gives almost direct calls of numpy C code)
    # numba is perfect for writing small pieces of code (that difficult or imposible to express in Polars) with numpy objects
    # instead rewriting on Rust (to not increase complexity of project and still take huge performance boost)
    @staticmethod
    @jit(nopython=True)
    def compute_path_distances(data_matrix, distance_matrix):

        unique_sample_ids = np.unique(data_matrix[:, 0])
        n_samples = unique_sample_ids.shape[0]
        sample_size = data_matrix.shape[0] // n_samples
        path_distances = np.zeros((n_samples,), dtype=np.float64)

        # using some optimizations (avoiding filtering comparison in each loop) to make
        # score calculation time linear (look closely into loops structure) for the current population / candidates batch
        for sample_id in unique_sample_ids:
            #sample_matrix = data_matrix[data_matrix[:, 0] == sample_id]
            sample_matrix = data_matrix[sample_id * sample_size : (sample_id + 1) * sample_size]

            planning_stop_ids = sample_matrix[:, 1]
            current_path_distance = 0
            current_path_distance += distance_matrix[0][planning_stop_ids[0]]
            current_path_distance += distance_matrix[planning_stop_ids[-1]][0]
            for i in range(1, len(planning_stop_ids)):
                from_id = planning_stop_ids[i - 1]
                to_id = planning_stop_ids[i]
                current_path_distance += distance_matrix[from_id][to_id]

            path_distances[sample_id] += current_path_distance

        return path_distances

    ############################################################################
    # experimental try to use dfs for storing distance matrix inside dataframes

    """def minimize_distance(self, planning_entity_dfs, problem_fact_dfs):

        path_stops_df = planning_entity_dfs["path_stops"]
        edge_distances_df = problem_fact_dfs["edge_distances"]

        path_distances = (
            path_stops_df
            .rename({"location_list_id": "from_stop"})
            .with_columns(
                pl.col("from_stop").shift(-1).alias("to_stop")
            )
            .join(edge_distances_df, on=["from_stop", "to_stop"])
            .group_by("sample_id")
            .agg(pl.col("distance").sum())
            .sort("sample_id")
        )

        path_distances = path_distances["distance"].to_list()

        scores = []
        for path_distance in path_distances:
            current_score = HardSoftScore(0, path_distance)
            scores.append( current_score )

        return scores"""
