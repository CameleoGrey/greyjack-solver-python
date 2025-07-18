# FILE: greynet/collectors/max_collector.py
from __future__ import annotations
import bisect
from collections import Counter
from .base_collector import BaseCollector

class MaxCollector(BaseCollector):
    """
    A collector that efficiently finds the maximum value from a group.
    It supports efficient insertion and retraction of items.
    """
    def __init__(self, mapping_function):
        self._mapping_function = mapping_function
        self._counts = Counter()
        self._sorted_keys = []

    def insert(self, item):
        value = self._mapping_function.apply(item)
        
        if self._counts[value] == 0:
            bisect.insort_left(self._sorted_keys, value)
            
        self._counts[value] += 1
        
        def undo():
            self._counts[value] -= 1
            if self._counts[value] == 0:
                del self._counts[value]
                key_index = bisect.bisect_left(self._sorted_keys, value)
                if key_index < len(self._sorted_keys) and self._sorted_keys[key_index] == value:
                    self._sorted_keys.pop(key_index)
        return undo

    def result(self):
        """Returns the maximum value in O(1) time."""
        return self._sorted_keys[-1] if self._sorted_keys else None

    def is_empty(self):
        return not self._sorted_keys
