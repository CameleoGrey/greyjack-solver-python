# greynet/collectors/count_collector.py
from ..collectors.base_collector import BaseCollector

class CountCollector(BaseCollector):
    def __init__(self):
        self._count = 0

    def insert(self, item):
        self._count += 1
        def undo():
            self._count -= 1
        return undo

    def result(self):
        return self._count

    def is_empty(self):
        return self._count == 0