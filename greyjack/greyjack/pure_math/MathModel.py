
from pprint import pprint
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
import random
import numpy as np

class MathModel():

    def __init__(self):
        self.variables = {}
        self.constraints = {}
        self.objectives = {}
        self.utility = {}
        self.variables = {}
        self.score = None
        self.constraint_weights = {}

        self.score_variant = ScoreVariants.HardSoftScore
        self.score_type = None
        self.score_calculator = ScoreCalculatorStub()
        self.variable_to_constraint_index = None

    def get_individual_hard_scores(self, absolute):

        hard_scores = {}
        for constraint_name in self.constraints.keys():
            if absolute:
                # for solving
                hard_scores[constraint_name] = abs(self.constraints[constraint_name].get_hard_score(self.variables, self.utility))
            else:
                # for exlaining
                hard_scores[constraint_name] = self.constraints[constraint_name].get_hard_score(self.variables, self.utility)

        return hard_scores

    def get_sum_hard_score(self, absolute):

        #print()
        #pprint(self.variables)
        #print()

        try:
            individual_hard_scores = self.get_individual_hard_scores(absolute)
            sum_hard_score = 0.0
            for constraint_name in individual_hard_scores.keys():
                sum_hard_score += individual_hard_scores[constraint_name]
        except Exception as e:
            print(e)


        return sum_hard_score

    def get_individual_soft_scores(self, is_fitting):

        soft_scores = {}
        for objective_name in self.objectives.keys():
            soft_scores[objective_name] = self.objectives[objective_name].get_soft_score(self.variables, self.utility, is_fitting)

        return soft_scores

    def get_sum_soft_score(self, is_fitting):

        try:
            sum_soft_score = 0
            individual_soft_scores = self.get_individual_soft_scores(is_fitting)
            for objective_name in individual_soft_scores.keys():
                sum_soft_score += individual_soft_scores[objective_name]
        
        except Exception as e:
            print(e)

        return sum_soft_score
    
    def _build_variable_to_constraint_index(self, variables_manager, var_name_to_arr_id_map, discrete_var_names):

        min_trials_count = 100
        variable_to_constraint_index = {}
        for var_name in self.variables.keys():
            
            variable_to_constraint_index[var_name] = set()

            value_before = self.variables[var_name]
            already_checked_values = set()
            current_trials_count = 0
            different_value_checked = False
            while current_trials_count < min_trials_count or not different_value_checked:
                
                value_after = variables_manager.get_column_random_value(var_name_to_arr_id_map[var_name])
                if var_name in discrete_var_names:
                    value_after = int(np.rint(value_after))
                if value_after == value_before:
                    continue
                else:
                    different_value_checked = True

                if value_after in already_checked_values:
                    current_trials_count += 1
                    continue
                else:
                    already_checked_values.add(value_after)

                for constraint_name in self.constraints.keys():
                    penalty_before = self.constraints[constraint_name].get_hard_score(self.variables, self.utility)
                    self.variables[var_name] = value_after
                    penalty_after = self.constraints[constraint_name].get_hard_score(self.variables, self.utility)
                    self.variables[var_name] = value_before

                    if abs(penalty_before) - abs(penalty_after) != 0.0:
                        variable_to_constraint_index[var_name].add(constraint_name)

                current_trials_count += 1

        return variable_to_constraint_index




    def explain_solution(self, gj_solution):

        solution_variables_dict = gj_solution.variable_values_dict
        for variable_name in solution_variables_dict.keys():
            variable_value = solution_variables_dict[variable_name]
            self.variables[variable_name] = variable_value

        hard_scores = self.get_individual_hard_scores(False)
        soft_scores = self.get_individual_soft_scores(False)

        print("Solution explanation:")
        print()
        print("--------------------------------------------------")
        print("Variables:")
        pprint(self.variables)
        print()
        print("--------------------------------------------------")
        print("Constraints violations: ")
        pprint(hard_scores)
        print()
        print("--------------------------------------------------")
        print("Objectives: ")
        pprint(soft_scores)
        print()

        pass



# filthy way to not rewrite core OOP Agent code
class ScoreCalculatorStub():
    def __init__(self):
        self.is_incremental = None
        pass