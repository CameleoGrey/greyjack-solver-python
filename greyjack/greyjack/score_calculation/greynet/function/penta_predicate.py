# greynet/function/penta_predicate.py
from abc import ABC, abstractmethod

class PentaPredicate(ABC):
    @abstractmethod
    def test(self, a, b, c, d, e):
        pass
