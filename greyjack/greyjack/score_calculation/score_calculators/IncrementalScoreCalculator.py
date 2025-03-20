
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.agents.base.individuals.IndividualSimple import IndividualSimple
from greyjack.agents.base.individuals.IndividualHardSoft import IndividualHardSoft
from greyjack.agents.base.individuals.IndividualHardMediumSoft import IndividualHardMediumSoft
from greyjack.greyjack import sum_simple_scores, sum_hard_soft_scores, sum_hard_medium_soft_scores

class IncrementalScoreCalculator:
    def __init__(self):
        self.constraints = {}
        self.constraint_weights = {}
        self.utility_objects = {}
        self.prescoring_functions = {}

        self.score_type = None
        self.score_variant = None
        self.is_incremental = True
        self.constraints_names_list = None
        self.scores_summation_function = None

    def add_constraint(self, constraint_name, constraint_function):
        self.constraints[constraint_name] = constraint_function
        if constraint_name not in self.constraint_weights:
            self.constraint_weights[constraint_name] = 1.0

    def remove_constraint(self, constraint_name):
        if constraint_name in self.constraints:
            del self.constraints[constraint_name]

    def set_constraint_weights(self, constraint_weights):
        self.constraint_weights = constraint_weights

    def add_utility_object(self, utility_object_name, utility_object):
        self.utility_objects[utility_object_name] = utility_object

    def remove_utility_object(self, utility_object_name):
        if utility_object_name in self.utility_objects:
            del self.utility_objects[utility_object_name]

    def add_prescoring_function(self, function_name, function):
        self.prescoring_functions[function_name] = function

    def remove_prescoring_function(self, function_name):
        if function_name in self.prescoring_functions:
            del self.prescoring_functions[function_name]

    def get_score(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):

        if self.score_variant is None:
            raise Exception("score_variant in PlainScoreCalculator is None. Set the score variant inside score calculator class. Warning! Use the same related score type inside all constraints.")
        else:
            if self.score_variant == ScoreVariants.SimpleScore:
                self.score_type = SimpleScore
                self.scores_summation_function = sum_simple_scores
            if self.score_variant == ScoreVariants.HardSoftScore:
                self.score_type = HardSoftScore
                self.scores_summation_function = sum_hard_soft_scores
            if self.score_variant == ScoreVariants.HardMediumSoftScore:
                self.score_type = HardMediumSoftScore
                self.scores_summation_function = sum_hard_medium_soft_scores

        for prescoring_function in self.prescoring_functions.values():
            prescoring_function(planning_entity_dfs, problem_fact_dfs)

        if self.constraints_names_list is None:
            self.constraints_names_list = list(self.constraints.keys())
            
        scores_vec = [self.constraints[name](planning_entity_dfs, problem_fact_dfs, delta_dfs) for name in self.constraints_names_list]
        scores = self.scores_summation_function(scores_vec, self.constraint_weights, self.constraints_names_list)

        return scores