

from greyjack.score_calculation.score_calculators.PlainScoreCalculator import PlainScoreCalculator
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl


class PlainScoreCalculator(PlainScoreCalculator):
    def __init__(self):

        super().__init__()

        self.score_variant = ScoreVariants.HardSoftScore

        self.add_constraint("some_constraint_function", self.some_constraint_function)

        pass
    
    def some_constraint_function(self, planning_entity_dfs, problem_fact_dfs):

        print(planning_entity_dfs["jobs"])
        print()
        print(problem_fact_dfs["lines"])
        print()
        print(problem_fact_dfs["products"])
        print()

        raise Exception("Plain scoring isn't already implemented for this task")

        return scores
