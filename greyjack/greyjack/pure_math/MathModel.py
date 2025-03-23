
from pprint import pprint
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants

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
    
    #def update_model_by_solution(self, gj_solution):


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