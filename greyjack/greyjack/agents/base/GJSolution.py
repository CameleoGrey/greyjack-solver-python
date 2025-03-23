
import numpy as np

class GJSolution():
    def __init__(self, variable_names, discrete_ids, variable_values, score_list, score_precision):

        if discrete_ids is not None:
            for discrete_id in discrete_ids:
                variable_values[discrete_id] = int(np.rint(variable_values[discrete_id]))
        
        if score_precision is not None:
            for i in range(len(score_list)):
                score_list[i] = round(score_list[i], score_precision[i])

        self.variable_values_dict = {}
        for var_name, var_value in zip(variable_names, variable_values):
            self.variable_values_dict[var_name] = var_value

        self.score = score_list

    def __str__(self):

        solution_string = ""
        for var_name, var_value in self.variable_values_dict.items():
            var_string = var_name + " = {}".format( var_value )
            solution_string += var_string + "\n"
        solution_string += "-----------------------------------------\n"
        solution_string += "Score: " + " | ".join([str(score_value) for score_value in self.score]) + "\n"

        return solution_string
