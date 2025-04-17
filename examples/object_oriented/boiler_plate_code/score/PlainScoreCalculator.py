

from greyjack.score_calculation.score_calculators.PlainScoreCalculator import PlainScoreCalculator
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl


class PlainScoreCalculator(PlainScoreCalculator):
    def __init__(self):

        super().__init__()

        self.score_variant = ScoreVariants.SimpleScore

        self.add_constraint("some_constraint_function", self.some_constraint_function)

        pass
    
    def some_constraint_function(self, planning_entity_dfs, problem_fact_dfs):

        return scores
