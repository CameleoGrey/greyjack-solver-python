
# greynet/function/supplier.py

from abc import ABC, abstractmethod

class Supplier(ABC):
    @abstractmethod
    def get(self):
        pass