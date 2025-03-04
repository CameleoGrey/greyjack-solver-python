
from greyjack.agents.termination_strategies.TerminationStrategy import TerminationStrategy

class ScoreLimit(TerminationStrategy):
    def __init__(self, score_to_compare):

        self.score_to_compare = score_to_compare
        self.current_best_score = None

        pass

    def update(self, agent):
        
        self.current_best_score = agent.current_top_individual.score

        pass

    def is_accomplish(self):

        if self.current_best_score <= self.score_to_compare:
            return True

        return False
    
    def get_accomplish_rate(self):

        accomplish_rate = self.current_best_sget_fitness_value() / (self.score_to_compare.get_fitness_value() + 1e-10)

        return accomplish_rate