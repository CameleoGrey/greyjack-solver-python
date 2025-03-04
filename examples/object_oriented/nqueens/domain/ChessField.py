

class ChessField():
    def __init__(self, n, queens):
        self.n = n
        self.queens = queens
        pass

    def __str__(self):

        field_string = []
        for i in range(self.n):
            row_string = []
            for j in range(self.n):
                row_string.append( "-" )
            row_string.append("\n")
            field_string.append(row_string)

        for queen in self.queens:
            row_id = queen.row.row_id
            column_id = queen.column.column_id
            field_string[row_id][column_id] = "+"

        for i in range(self.n):
            row_string = field_string[i]
            row_string = " ".join( row_string )
            field_string[i] = row_string
        field_string = " ".join(field_string)
        field_string = " " + field_string

        return field_string
