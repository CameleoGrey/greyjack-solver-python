

# rewrited by LLM from Rust to Python
# TODO: fix errors
class IncrementalScoreCalculator:
    def __init__(self):
        self.constraints = {}
        self.constraint_weights = {}
        self.utility_objects = {}
        self.prescoring_functions = {}

    def add_constraint(self, constraint_name, constraint_function):
        self.constraints[constraint_name] = constraint_function
        if constraint_name not in self.constraint_weights:
            self.constraint_weights[constraint_name] = 1.0

    def remove_constraint(self, constraint_name):
        self.constraints.pop(constraint_name, None)

    def set_constraint_weights(self, constraint_weights):
        self.constraint_weights = constraint_weights

    def add_utility_object(self, utility_object_name, utility_object):
        self.utility_objects[utility_object_name] = utility_object

    def remove_utility_object(self, utility_object_name):
        self.utility_objects.pop(utility_object_name, None)

    def add_prescoring_function(self, function_name, function):
        self.prescoring_functions[function_name] = function

    def remove_prescoring_function(self, function_name):
        self.prescoring_functions.pop(function_name, None)

    def get_score(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):
        for prescoring_function in self.prescoring_functions.values():
            prescoring_function(planning_entity_dfs, problem_fact_dfs, delta_dfs, self.utility_objects)

        constraint_names = list(self.constraints.keys())

        scores_vec = []
        for constraint_name in constraint_names:
            constraint_function = self.constraints[constraint_name]
            current_score_vec = constraint_function(planning_entity_dfs, problem_fact_dfs, delta_dfs, self.utility_objects)
            scores_vec.append(current_score_vec)

        constraints_count = len(scores_vec)
        samples_count = len(scores_vec[0])
        scores = []
        for j in range(samples_count):
            sample_sum_score = scores_vec[i][j].get_null_score()
            for i in range(constraints_count):
                constraint_weight = self.constraint_weights[constraint_names[i]]
                weighted_score = scores_vec[i][j].mul(constraint_weight)
                sample_sum_score += weighted_score
            scores.append(sample_sum_score)

        return scores