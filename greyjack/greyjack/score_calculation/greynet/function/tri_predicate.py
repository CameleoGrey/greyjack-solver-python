# greynet/function/tri_predicate.py
from abc import ABC, abstractmethod

class TriPredicate(ABC):
    @abstractmethod
    def test(self, a, b, c):
        pass