# greynet/collectors/base_collector.py
from abc import ABC, abstractmethod

class BaseCollector(ABC):
    @abstractmethod
    def insert(self, item):
        """
        Adds an item to the collection and returns an undo function.

        The undo function is critical for retract operations, allowing the
        collector to precisely reverse the effect of an insertion.
        """
        pass

    @abstractmethod
    def result(self):
        """
        Returns the current result of the aggregation.
        """
        pass

    @abstractmethod
    def is_empty(self):
        """
        Returns True if the collection is empty, False otherwise.
        """
        pass