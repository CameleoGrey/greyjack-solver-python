
import numpy as np

class GJSolution():
    def __init__(self, variable_values_dict, score):
        self.variable_values_dict = variable_values_dict
        for var_name in self.variable_values_dict.keys():
            var_value = self.variable_values_dict[var_name]

            if "float" in str(type(var_value)):
                var_value = float( var_value )
            if "int" in str(type(var_value)):
                var_value = int( var_value )

            self.variable_values_dict[var_name] = var_value


        self.score = score

    def __repr__(self):

        solution_string = ""

        for var_name in self.variable_values_dict.keys():
            var_string = var_name + " = {}".format( self.variable_values_dict[var_name] )
            solution_string += var_string + "\n"

        solution_string += "Score: " + str(self.score) + "\n"

        return solution_string
    
    def __eq__(self, other):
        return self.score == other.score

    def __ne__(self, other):
        return self.score != other.score

    def __le__(self, other):
        return self.score <= other.score

    def __ge__(self, other):
        return self.score >= other.score

    def __lt__(self, other):
        return self.score < other.score

    def __gt__(self, other):
        return self.score > other.score