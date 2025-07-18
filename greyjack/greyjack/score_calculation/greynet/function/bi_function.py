# greynet/function/bi_function.py
from abc import ABC, abstractmethod

class BiFunction(ABC):
    @abstractmethod
    def apply(self, a, b):
        pass