

class CotwinBase():
    def __init__(self):
        self.planning_entities = {}
        self.problem_facts = {}
        self.score_calculators = {}
        pass

    def _set_solution_status(self, status):
        self.solved = status

    def add_planning_entities_list(self, planning_entities_list, name):
        self.planning_entities[name] = planning_entities_list
        pass

    def add_problem_facts_list(self, problem_facts_list, name):
        self.problem_facts[name] = problem_facts_list
        pass

    def add_score_calculator(self, score_calculator, name):
        self.score_calculators[name] = score_calculator
        pass

    def get_score(self, planning_entity_dfs, problem_fact_dfs):

            scores_dict = {}
            for score_calculator_name in self.score_calculators.keys():
                scores_dict[score_calculator_name] = (
                    self.score_calculators[score_calculator_name].get_score(planning_entity_dfs, problem_fact_dfs, batch_mode=True))

            scores_values = list(scores_dict.values())
            score_type = type(scores_values[0][0])
            sum_score = [score_type() for i in range(len(scores_values[0]))]
            for score_name in scores_dict.keys():
                current_score_list = scores_dict[score_name]
                for i in range(len(current_score_list)):
                    sum_score[i] += current_score_list[i]

            return sum_score