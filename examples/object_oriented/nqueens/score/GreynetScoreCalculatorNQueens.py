# file: GreynetScoreCalculatorNQueens.py

from greyjack.score_calculation.score_calculators.GreynetScoreCalculator import GreynetScoreCalculator
from greyjack.score_calculation.greynet.builder import ConstraintBuilder
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.score_calculation.greynet.common.joiner_type import JoinerType
from ..cotwin.CotQueen import CotQueen

cb = ConstraintBuilder(name="NQueens", score_class=SimpleScore)

@cb.constraint("Same Row", default_weight=1.0)
def same_row():
    return (
        cb.for_each(CotQueen)
        .join(
            cb.for_each(CotQueen),
            JoinerType.EQUAL,
            lambda q: q.row_id,
            lambda q: q.row_id
        )
        .filter(lambda q1, q2: q1.queen_id < q2.queen_id)
        .penalize_simple(1)
    )

@cb.constraint("Ascending Diagonal", default_weight=1.0)
def ascending_diagonal():
    return (
        cb.for_each(CotQueen)
        .join(
            cb.for_each(CotQueen),
            JoinerType.EQUAL,
            lambda q: q.column_id - q.row_id,
            lambda q: q.column_id - q.row_id
        )
        .filter(lambda q1, q2: q1.queen_id < q2.queen_id)
        .penalize_simple(1)
    )

@cb.constraint("Descending Diagonal", default_weight=1.0)
def descending_diagonal():
    return (
        cb.for_each(CotQueen)
        .join(
            cb.for_each(CotQueen),
            JoinerType.EQUAL,
            lambda q: q.column_id + q.row_id,
            lambda q: q.column_id + q.row_id
        )
        .filter(lambda q1, q2: q1.queen_id < q2.queen_id)
        .penalize_simple(1)
    )

greynet_score_calculator_nqueens = GreynetScoreCalculator(constraint_builder=cb, score_variant=ScoreVariants.SimpleScore)