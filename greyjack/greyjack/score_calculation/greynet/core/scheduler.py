# greynet/core/scheduler.py
from abc import ABC, abstractmethod

class Scheduler(ABC):
    def __init__(self, node_map):
        self._node_map = node_map

    @abstractmethod
    def schedule(self, tuple_):
        pass

    @abstractmethod
    def fire_all(self):
        pass