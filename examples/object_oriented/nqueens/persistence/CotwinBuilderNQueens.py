


from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from examples.object_oriented.nqueens.cotwin.NQueensCotwin import NQueensCotwin
from examples.object_oriented.nqueens.score.PlainScoreCalculatorNQueens import PlainScoreCalculatorNQueens
from examples.object_oriented.nqueens.score.IncrementalScoreCalculatorNQueens import IncrementalScoreCalculatorNQueens
from examples.object_oriented.nqueens.cotwin.CotQueen import CotQueen
from greyjack.variables.GJInteger import GJInteger


class CotwinBuilderNQueens(CotwinBuilderBase):
    def __init__(self, use_incremental_score_calculator):
        self.use_incremental_score_calculator = use_incremental_score_calculator
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
            cot_queens.append( cot_queen )

        nqueens_cotwin = NQueensCotwin()
        nqueens_cotwin.add_planning_entities_list( cot_queens, "queens" )
        if self.use_incremental_score_calculator:
            nqueens_cotwin.set_score_calculator( IncrementalScoreCalculatorNQueens() )
        else:
            nqueens_cotwin.set_score_calculator( PlainScoreCalculatorNQueens() )

        return nqueens_cotwin




