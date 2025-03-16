

class CotwinBase():
    def __init__(self):
        self.planning_entities = {}
        self.problem_facts = {}
        self.score_calculator = None
        pass

    def _set_solution_status(self, status):
        self.solved = status

    def add_planning_entities_list(self, planning_entities_list, name):
        self.planning_entities[name] = planning_entities_list
        pass

    def add_problem_facts_list(self, problem_facts_list, name):
        self.problem_facts[name] = problem_facts_list
        pass

    def set_score_calculator(self, score_calculator):
        self.score_calculator = score_calculator
        pass

    def get_score_plain(self, planning_entity_dfs, problem_fact_dfs):
        return self.score_calculator.get_score(planning_entity_dfs, problem_fact_dfs)
    
    def get_score_incremental(self, planning_entity_dfs, problem_fact_dfs, delta_dfs):
        return self.score_calculator.get_score(planning_entity_dfs, problem_fact_dfs, delta_dfs)