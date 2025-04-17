
from greyjack.score_calculation.score_calculators.IncrementalScoreCalculator import IncrementalScoreCalculator
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl
import numpy as np
import numba
from numba import jit, int64, float64, vectorize


class IncrementalScoreCalculator(IncrementalScoreCalculator):
    def __init__(self):
        super().__init__()
        self.score_variant = ScoreVariants.SimpleScore
        self.add_constraint("some_constraint_function", self.some_constraint_function)
        pass

    def some_constraint_function(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):

        return scores