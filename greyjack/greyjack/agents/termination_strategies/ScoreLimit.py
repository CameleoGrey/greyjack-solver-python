
from greyjack.agents.termination_strategies.TerminationStrategy import TerminationStrategy

class ScoreLimit(TerminationStrategy):
    def __init__(self, score_to_compare):

        self.score_to_compare = score_to_compare
        self.current_best_score = None

        self.is_started = False

        pass

    def update(self, agent):
        
        # This strange thing below is necessary, because all wrapped 
        # into Py Rust objects can't be pickled (necessary when launching agent jobs)
        # From other side, normal import causes some recursive import error
        if not self.is_started:
            self.is_started = True
            if len(self.score_to_compare) == 1:
                from greyjack.score_calculation.scores.SimpleScore import SimpleScore
                self.score_to_compare = SimpleScore(*self.score_to_compare)
            elif len(self.score_to_compare) == 2:
                from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
                self.score_to_compare = HardSoftScore(*self.score_to_compare)
            elif len(self.score_to_compare) == 3:
                from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore
                self.score_to_compare = HardMediumSoftScore(*self.score_to_compare)
            else:
                raise Exception("Something wrong with score. Check criterion definition.")
        
        self.current_best_score = agent.agent_top_individual.score

        pass

    def is_accomplish(self):

        if self.current_best_score <= self.score_to_compare:
            return True

        return False
    
    def get_accomplish_rate(self):

        accomplish_rate = self.current_best_score.get_fitness_value() / (self.score_to_compare.get_fitness_value() + 1e-10)

        return accomplish_rate