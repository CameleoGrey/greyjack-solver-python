


from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from examples.object_oriented.nqueens.cotwin.NQueensCotwin import NQueensCotwin
from examples.object_oriented.nqueens.score.PlainScoreCalculatorNQueens import PlainScoreCalculatorNQueens
from examples.object_oriented.nqueens.score.IncrementalScoreCalculatorNQueens import IncrementalScoreCalculatorNQueens
from examples.object_oriented.nqueens.score.GreynetScoreCalculatorNQueens import greynet_score_calculator_nqueens
from examples.object_oriented.nqueens.cotwin.CotQueen import CotQueen
from greyjack.variables.GJInteger import GJInteger


class CotwinBuilderNQueens(CotwinBuilderBase):
    def __init__(self, scorer_name):
        self.scorer_name = scorer_name
        pass

    def build_cotwin(self, domain_model, is_already_initialized):

        n = domain_model.n
        queens = domain_model.queens

        cot_queens = []
        for i in range( len(queens) ):
            queen_id = i
            column_id = i
            planning_row_id = GJInteger(0, n-1, False, queens[i].row.row_id, None)
            cot_queen = CotQueen( queen_id, planning_row_id, column_id )
            cot_queen.greynet_fact_id = queen_id
            cot_queens.append( cot_queen )

        nqueens_cotwin = NQueensCotwin()
        nqueens_cotwin.add_planning_entities_list( cot_queens, "queens" )
        if self.scorer_name == "plain":
            nqueens_cotwin.set_score_calculator( PlainScoreCalculatorNQueens() )
        elif self.scorer_name == "pseudo":
            nqueens_cotwin.set_score_calculator( IncrementalScoreCalculatorNQueens() )
        elif self.scorer_name == "greynet":
            nqueens_cotwin.set_score_calculator( greynet_score_calculator_nqueens )
        else:
            raise ValueError("Available score calculators: plain, pseudo, greynet")

        return nqueens_cotwin




