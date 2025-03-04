
from greyjack.agents.termination_strategies.TerminationStrategy import TerminationStrategy

class StepsLimit(TerminationStrategy):
    def __init__(self, step_count_limit=10000):

        self.step_count_limit = step_count_limit
        self.steps_made = 0

        pass

    def update(self, agent):
        self.steps_made += 1
        pass

    def is_accomplish(self):

        if self.steps_made > self.step_count_limit:
            return True

        return False
    
    def get_accomplish_rate(self):

        accomplish_rate = float(self.steps_made) / float(self.step_count_limit)

        return accomplish_rate