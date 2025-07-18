# greynet/function/quad_function.py
from abc import ABC, abstractmethod

class QuadFunction(ABC):
    @abstractmethod
    def apply(self, a, b, c, d):
        pass