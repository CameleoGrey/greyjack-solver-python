

from greyjack.score_calculation.score_calculators.PlainScoreCalculator import PlainScoreCalculator
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
from numba import jit
import numpy as np

class PlainScoreCalculatorCB( PlainScoreCalculator ):

    def __init__(self):
        super().__init__()

        self.score_variant = ScoreVariants.HardSoftScore

        self.add_constraint("all_in_one_constraint", self.all_in_one_constraint)

        pass

    def all_in_one_constraint(self, planning_entity_dfs, problem_fact_dfs):

        processes_df = planning_entity_dfs["processes"]
        computers_df = problem_fact_dfs["computers"]

        scores  = (
            processes_df
            .lazy()

            .group_by(["sample_id", "computer_id"])
            .agg([
                pl.col("cpu_power_req").sum().alias("total_cpu_consumption"),
                pl.col("memory_size_req").sum().alias("total_memory_consumption"),
                pl.col("network_bandwidth_req").sum().alias("total_network_consumption"),
            ])

            .join(computers_df.lazy(), on="computer_id", how="inner")
            
            .with_columns([
                (pl.col("total_cpu_consumption") - pl.col("cpu_power")).alias("cpu_penalty"),
                (pl.col("total_memory_consumption") - pl.col("memory_size")).alias("memory_penalty"),
                (pl.col("total_network_consumption") - pl.col("network_bandwidth")).alias("network_penalty"),
            ])


            .with_columns([
                pl.when(pl.col("cpu_penalty") > 0).then(pl.col("cpu_penalty")).otherwise(0).alias("cpu_penalty"),
                pl.when(pl.col("memory_penalty") > 0).then(pl.col("memory_penalty")).otherwise(0).alias("memory_penalty"),
                pl.when(pl.col("network_penalty") > 0).then(pl.col("network_penalty")).otherwise(0).alias("network_penalty"),
            ])

            .group_by(["sample_id", "computer_id", "cost"])
            .agg([
                pl.col("cpu_penalty").sum().alias("cpu_penalty"),
                pl.col("memory_penalty").sum().alias("memory_penalty"),
                pl.col("network_penalty").sum().alias("network_penalty"),
            ])

            .group_by(["sample_id"])
            .agg([
                (pl.col("cpu_penalty").sum() + pl.col("memory_penalty").sum() + pl.col("network_penalty").sum()).alias("hard_score"),
                pl.col("cost").sum().alias("soft_score"),
            ])

            .sort("sample_id", descending=[False])

            .collect()
        )

        scores = scores[["hard_score", "soft_score"]].to_numpy()
        scores = [HardSoftScore(score[0], score[1]) for score in scores]

        return scores
