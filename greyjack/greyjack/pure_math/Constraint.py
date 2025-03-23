

class Constraint():
    def __init__(self, left_part, comparator="==", right_part=lambda v, u: 0):
        self.a = left_part
        self.b = right_part
        self.penalty_function = self._define_penalty( comparator )

    def get_hard_score(self, variables, utility_objects):

        a = self.a(variables, utility_objects)
        b = self.b(variables, utility_objects)
        hard_score = self.penalty_function(a, b)
        return hard_score
    def _define_penalty(self, comparator_string):

        if (comparator_string == "=="): return self._equal_penalty
        if (comparator_string == "<="): return self._less_or_equal_penalty
        if (comparator_string == ">="): return self._greater_or_equal_penalty
        if (comparator_string == "<"): return self._strict_less_penalty
        if (comparator_string == ">"): return self._strict_greater_penalty
        raise Exception("Comparator can be only: ==, <=, >=, <, >")

    def _equal_penalty(self, a, b):
        return abs( a - b )

    def _less_or_equal_penalty(self, a, b):
        return 0 if a <= b else a - b

    def _greater_or_equal_penalty(self, a, b):
        return 0 if a >= b else b - a

    def _strict_less_penalty(self, a, b):
        return 0 if a < b else a - b

    def _strict_greater_penalty(self, a, b):
        return 0 if a > b else b - a