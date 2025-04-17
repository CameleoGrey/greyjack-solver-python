

from greyjack.score_calculation.score_calculators.PlainScoreCalculator import PlainScoreCalculator
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import polars as pl


class PlainScoreCalculator(PlainScoreCalculator):
    def __init__(self):

        super().__init__()

        self.score_variant = ScoreVariants.HardSoftScore

        self.add_constraint("some_constraint_function", self.some_constraint_function)

        pass
    
    def some_constraint_function(self, planning_entity_dfs, problem_fact_dfs):

        shifts_df = planning_entity_dfs["shifts"]
        employees_df = problem_fact_dfs["employees"]

        print(shifts_df)
        print()
        print(employees_df)

        raise Exception("Plain scoring doesn't implement for Employee Scheduling")
