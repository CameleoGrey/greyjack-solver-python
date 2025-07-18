# greynet/function/bi_predicate.py
from abc import ABC, abstractmethod

class BiPredicate(ABC):
    @abstractmethod
    def test(self, a, b):
        pass