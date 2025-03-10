

from greyjack.score_calculation.score_calculators.PlainScoreCalculator import PlainScoreCalculator
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl

#import os
#os.environ["POLARS_MAX_THREADS"] = "1"
#os.environ["MIMALLOC_ABANDONED_PAGE_RESET"] = "1"


class NQueensScoreCalculator(PlainScoreCalculator):
    def __init__(self):

        super().__init__()

        self.score_variant = ScoreVariants.SimpleScore

        #self.add_constraint("different_rows", self.different_rows)
        #self.add_constraint("different_descending_diagonals", self.different_descending_diagonals)
        #self.add_constraint("different_ascending_diagonals", self.different_ascending_diagonals)

        self.add_constraint("all_different", self.all_different)

        pass
    
    def all_different(self, planning_entity_dfs, problem_fact_dfs):

        queens_df = planning_entity_dfs["queens"]
        same_row_id_counts = (
            queens_df
            .lazy()
            .with_columns(
                (pl.col("column_id") + pl.col("row_id")).alias("desc_id"),
                (pl.col("column_id") - pl.col("row_id")).alias("asc_id"),
            )
            .group_by("sample_id")
            .agg(
                (pl.col("row_id").len() - pl.col("row_id").n_unique()).alias("row_conflicts_count"),
                (pl.col("desc_id").len() - pl.col("desc_id").n_unique()).alias("desc_conflicts_count"),
                (pl.col("asc_id").len() - pl.col("asc_id").n_unique()).alias("asc_conflicts_count")
            )
            .with_columns((pl.col("row_conflicts_count") + pl.col("desc_conflicts_count") + pl.col("asc_conflicts_count")).alias("sum_conflicts"))
            .sort("sample_id")
            .collect()
        )
        
        scores = same_row_id_counts["sum_conflicts"].to_list()
        scores = [SimpleScore(score) for score in scores]

        return scores

    def prepare_for_scoring(self, planning_entity_dfs, problem_fact_dfs):
        #self.adjust_queen_df( planning_entity_dfs, problem_fact_dfs )
        pass

    def adjust_queen_df(self, planning_entity_dfs, problem_fact_dfs):
        queens_df = planning_entity_dfs["queens"]

        queens_df = queens_df.with_columns(
            (pl.col("column_id") + pl.col("row_id")).alias( "descending_diagonal_id" ),
            (pl.col("column_id") - pl.col("row_id")).alias( "ascending_diagonal_id" )
        )

        planning_entity_dfs["queens"] = queens_df

    def different_rows(self, planning_entity_dfs, problem_fact_dfs):

        queens_df = planning_entity_dfs["queens"]
        same_row_id_counts = (
            queens_df
            .lazy()
            .group_by("sample_id", "row_id")
            .agg((pl.col("queen_id").count() - 1).alias("conflicts_count"))
            .group_by("sample_id")
            .agg(pl.col("conflicts_count").sum())
            .sort("sample_id")
            .collect()
        )

        scores = same_row_id_counts["conflicts_count"].to_list()
        scores = [SimpleScore(score) for score in scores]

        return scores

    def different_descending_diagonals(self, planning_entity_dfs, problem_fact_dfs):
        queens_df = planning_entity_dfs["queens"]
        same_row_id_counts = (
            queens_df
            .lazy()
            .with_columns((pl.col("column_id") + pl.col("row_id")).alias("desc_id"))
            .group_by("sample_id", "desc_id")
            .agg((pl.col("queen_id").count() - 1).alias("conflicts_count"))
            .group_by("sample_id")
            .agg(pl.col("conflicts_count").sum())
            .sort("sample_id")
            .collect()
        )

        scores = same_row_id_counts["conflicts_count"].to_list()
        scores = [SimpleScore(score) for score in scores]

        return scores

    def different_ascending_diagonals(self, planning_entity_dfs, problem_fact_dfs):
        queens_df = planning_entity_dfs["queens"]

        same_row_id_counts = (
            queens_df
            .lazy()
            .with_columns((pl.col("column_id") - pl.col("row_id")).alias("asc_id"))
            .group_by("sample_id", "asc_id")
            .agg((pl.col("queen_id").count() - 1).alias("conflicts_count"))
            .group_by("sample_id")
            .agg(pl.col("conflicts_count").sum())
            .sort("sample_id")
            .collect()
        )

        scores = same_row_id_counts["conflicts_count"].to_list()
        scores = [SimpleScore(score) for score in scores]

        return scores

