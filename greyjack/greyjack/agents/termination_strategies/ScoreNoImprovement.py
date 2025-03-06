
from greyjack.agents.termination_strategies.TerminationStrategy import TerminationStrategy
from datetime import datetime

class ScoreNoImprovement(TerminationStrategy):
    def __init__(self, time_seconds_limit=15):

        self.time_seconds_limit = time_seconds_limit
        self.start_time = None
        self.current_best_score = None
        self.time_delta = None

        pass

    def update(self, agent):
        
        if self.start_time is None:
            self.start_time = datetime.now()
            self.time_delta = (self.start_time - self.start_time).seconds
            self.current_best_score = agent.agent_top_individual.score
            return
        
        # to prevent updates from migrants
        if self.is_accomplish():
            return
        
        current_score = agent.agent_top_individual.score

        if current_score < self.current_best_score:
            self.current_best_score = current_score
            self.start_time = datetime.now()
            self.time_delta = (self.start_time - self.start_time).seconds
        else:
            self.time_delta = (datetime.now() - self.start_time).seconds

        pass

    def is_accomplish(self):

        if self.time_delta >= self.time_seconds_limit:
            return True

        return False
    
    def get_accomplish_rate(self):

        accomplish_rate = float(self.time_delta) / float(self.time_seconds_limit)

        return accomplish_rate