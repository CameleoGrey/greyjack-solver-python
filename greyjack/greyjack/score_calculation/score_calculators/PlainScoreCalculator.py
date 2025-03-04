

from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.SimpleScore import SimpleScore


class PlainScoreCalculator():
    def __init__(self):

        self.constraints = {}
        self.constraint_weights = {}
        self.utility_objects = {}

        pass

    def prepare_for_scoring(self, planning_entity_dfs, problem_fact_dfs):
        pass

    def get_score(self, planning_entity_dfs, problem_fact_dfs, batch_mode = False):

        self.prepare_for_scoring(planning_entity_dfs, problem_fact_dfs)

        scores_dict = {}
        for constraint_name in self.constraints.keys():
            scores_dict[constraint_name] = self.constraints[constraint_name](planning_entity_dfs, problem_fact_dfs)
            if constraint_name not in self.constraint_weights:
                self.constraint_weights[constraint_name] = 1

        scores_values = list(scores_dict.values())
        score_type = type(scores_values[0][0])
        if batch_mode:
            sum_score = [score_type() for i in range(len(scores_values[0]))]
            for score_name in scores_dict.keys():
                current_score_list = scores_dict[score_name]
                for i in range(len(current_score_list)):
                    sum_score[i] += current_score_list[i]
        else:
            sum_score = score_type()
            for score_name in scores_dict.keys():
                current_score = scores_dict[score_name][0]
                current_score = self.constraint_weights[score_name] * current_score
                sum_score += current_score

        return sum_score

    def remove_constraint(self, constraint_name):
        if constraint_name in self.constraints:
            del self.constraints[constraint_name]

