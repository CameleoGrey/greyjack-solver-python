
# greynet/collectors/avg_collector.py

from .base_collector import BaseCollector

class AvgCollector(BaseCollector):
    def __init__(self, mapping_function):
        self._mapping_function = mapping_function
        self._sum = 0.0
        self._count = 0

    def insert(self, item):
        value = float(self._mapping_function.apply(item))
        self._sum += value
        self._count += 1
        def undo():
            self._sum -= value
            self._count -= 1
        return undo

    def result(self):
        return self._sum / self._count if self._count > 0 else 0.0

    def is_empty(self):
        return self._count == 0
