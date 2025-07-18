# greynet/collectors/sum_collector.py
from ..collectors.base_collector import BaseCollector

class SumCollector(BaseCollector):
    def __init__(self, mapping_function):
        self._mapping_function = mapping_function
        self._total = 0
        self._count = 0 # Track item count to correctly handle emptiness

    def insert(self, item):
        value = self._mapping_function.apply(item)
        self._total += value
        self._count += 1
        def undo():
            self._total -= value
            self._count -= 1
        return undo

    def result(self):
        return self._total

    def is_empty(self):
        return self._count == 0