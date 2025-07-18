# greynet/function/quad_predicate.py
from abc import ABC, abstractmethod

class QuadPredicate(ABC):
    @abstractmethod
    def test(self, a, b, c, d):
        pass