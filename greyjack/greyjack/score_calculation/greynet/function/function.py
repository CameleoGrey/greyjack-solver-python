# greynet/function/function.py
from abc import ABC, abstractmethod

class Function(ABC):
    @abstractmethod
    def apply(self, value):
        pass