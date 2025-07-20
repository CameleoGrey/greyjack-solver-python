# greynet/function/tri_function.py
from abc import ABC, abstractmethod

class TriFunction(ABC):
    @abstractmethod
    def apply(self, a, b, c):
        pass