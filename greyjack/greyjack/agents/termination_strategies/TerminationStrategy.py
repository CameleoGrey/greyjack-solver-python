
from abc import ABC, abstractmethod

class TerminationStrategy(ABC):

    @abstractmethod
    def update(self, agent):
        pass
    
    @abstractmethod
    def is_accomplish(self):
        pass
    
    # how far from start of termination is the prcoess of solving
    @abstractmethod
    def get_accomplish_rate(self):
        pass