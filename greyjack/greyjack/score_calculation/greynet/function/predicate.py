# greynet/function/predicate.py
from abc import ABC, abstractmethod

class Predicate(ABC):
    @abstractmethod
    def test(self, value):
        pass