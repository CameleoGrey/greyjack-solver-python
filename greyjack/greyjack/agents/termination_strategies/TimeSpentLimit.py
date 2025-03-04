
from greyjack.agents.termination_strategies.TerminationStrategy import TerminationStrategy
from datetime import datetime

class TimeSpentLimit(TerminationStrategy):
    def __init__(self, time_seconds_limit=5*60):

        self.time_seconds_limit = time_seconds_limit
        self.start_time = None
        self.time_delta = None

        pass

    def update(self, agent):
        
        if self.start_time is None:
            self.start_time = datetime.now()
            self.time_delta = (self.start_time - self.start_time).seconds
            return

        self.time_delta = (datetime.now() - self.start_time).seconds

        pass

    def is_accomplish(self):

        if self.time_delta >= self.time_seconds_limit:
            return True

        return False
    
    def get_accomplish_rate(self):

        accomplish_rate = float(self.time_delta) / float(self.time_seconds_limit)

        return accomplish_rate