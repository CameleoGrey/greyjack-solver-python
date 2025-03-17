
import random

from greyjack.persistence.DomainBuilderBase import DomainBuilderBase
from examples.object_oriented.nqueens.domain.ChessField import ChessField
from examples.object_oriented.nqueens.domain.Position import Position
from examples.object_oriented.nqueens.domain.Row import Row
from examples.object_oriented.nqueens.domain.Column import Column
from examples.object_oriented.nqueens.domain.Queen import Queen


class DomainBuilderNQueens(DomainBuilderBase):

    def __init__(self, n, random_seed=45):
        super().__init__()

        self.n_queens = n
        self.random_seed = random_seed

    def build_domain_from_scratch(self):

        random.seed(self.random_seed)

        queens = []
        random_row_ids = list(range(self.n_queens))
        random.shuffle( random_row_ids )
        column_ids = list(range(self.n_queens))
        for i in range(self.n_queens):
            current_row_id = random_row_ids[i]
            current_column_id = column_ids[i]
            current_queen = Queen( Row(current_row_id), Column(current_column_id) )
            queens.append( current_queen )

        chess_field = ChessField( self.n_queens, queens )

        return chess_field
    
    def build_from_solution(self, solution, initial_domain=None):
        raise Exception("build_from_solution() not implemented for DomainBuilderNQueens")
    
    def build_from_domain(self, domain):
        return super().build_from_domain(domain)


