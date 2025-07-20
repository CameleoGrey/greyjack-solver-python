
from greyjack.score_calculation.greynet.greynet_fact import *

@greynet_fact
class CotQueen():
    def __init__(self, queen_id, row_id, column_id):
        self.queen_id = queen_id
        self.row_id = row_id
        self.column_id = column_id
        pass

    def __repr__(self):
        return str(self.column_id) + " | " + str(self.row_id) + " " + str(self.greynet_fact_id) 