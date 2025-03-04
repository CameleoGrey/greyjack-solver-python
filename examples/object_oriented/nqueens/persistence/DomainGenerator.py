
import random

from examples.object_oriented.nqueens.domain.ChessField import ChessField
from examples.object_oriented.nqueens.domain.Position import Position
from examples.object_oriented.nqueens.domain.Row import Row
from examples.object_oriented.nqueens.domain.Column import Column
from examples.object_oriented.nqueens.domain.Queen import Queen


class DomainGenerator():

    @staticmethod
    def generate_domain(n, random_seed=45):

        random.seed(random_seed)

        queens = []
        random_row_ids = list(range(n))
        random.shuffle( random_row_ids )
        column_ids = list(range(n))
        for i in range(n):
            current_row_id = random_row_ids[i]
            current_column_id = column_ids[i]
            current_queen = Queen( Row(current_row_id), Column(current_column_id) )
            queens.append( current_queen )

        chess_field = ChessField( n, queens )

        return chess_field


