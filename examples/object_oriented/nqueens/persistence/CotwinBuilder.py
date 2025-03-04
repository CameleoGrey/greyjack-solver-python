from examples.object_oriented.nqueens.cotwin.NQueensCotwin import NQueensCotwin
from examples.object_oriented.nqueens.score.NQueensScoreCalculator import NQueensScoreCalculator
from examples.object_oriented.nqueens.cotwin.CotQueen import CotQueen
from greyjack.variables.GJInteger import GJInteger


class CotwinBuilder():
    def __init__(self):
        pass

    def build_cotwin(self, domain_model):

        n = domain_model.n
        queens = domain_model.queens

        cot_queens = []
        for i in range( len(queens) ):
            queen_id = i
            column_id = i
            planning_row_id = GJInteger("queen_{}_row_id".format(queen_id), 0, n-1, False, queens[i].row.row_id, None)
            cot_queen = CotQueen( queen_id, planning_row_id, column_id )
            cot_queens.append( cot_queen )

        nqueens_cotwin = NQueensCotwin()
        nqueens_cotwin.add_planning_entities_list( cot_queens, "queens" )
        nqueens_cotwin.add_score_calculator( NQueensScoreCalculator(), "nqueens_score_calculator" )

        return nqueens_cotwin




