# file: nqueens_constraint_builder.py

from greyjack.score_calculation.score_calculators.GreynetScoreCalculator import GreynetScoreCalculator
from greyjack.score_calculation.greynet.builder import ConstraintBuilder
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from ..cotwin.CotQueen import CotQueen

cb = ConstraintBuilder(name="NQueens", score_class=SimpleScore)

@cb.constraint("Row Conflict", default_weight=1.0)
def row_conflict():
    return (
        cb.for_each_unique_pair(CotQueen)
        .filter(lambda q1, q2: q1.row_id == q2.row_id)
        .penalize_simple(1)
    )

@cb.constraint("Ascending Diagonal Conflict", default_weight=1.0)
def ascending_diagonal_conflict():
    return (
        cb.for_each_unique_pair(CotQueen)
        .filter(lambda q1, q2: (q1.row_id - q1.column_id) == (q2.row_id - q2.column_id))
        .penalize_simple(1)
    )

@cb.constraint("Descending Diagonal Conflict", default_weight=1.0)
def descending_diagonal_conflict():
    return (
        cb.for_each_unique_pair(CotQueen)
        .filter(lambda q1, q2: (q1.row_id + q1.column_id) == (q2.row_id + q2.column_id))
        .penalize_simple(1)
    )

greynet_score_calculator_nqueens = GreynetScoreCalculator(constraint_builder=cb, score_variant=ScoreVariants.SimpleScore)