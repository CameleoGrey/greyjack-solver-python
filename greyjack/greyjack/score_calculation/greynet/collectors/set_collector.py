# greynet/collectors/set_collector.py
from __future__ import annotations
from collections import Counter
from .base_collector import BaseCollector

class SetCollector(BaseCollector):
    """
    A collector that aggregates items into a set, ensuring uniqueness.
    It correctly handles the insertion and retraction of duplicate items.
    """
    def __init__(self):
        self._items = set()
        self._counter = Counter()

    def insert(self, item):
        """Adds an item to the set and tracks its reference count."""
        if self._counter[item] == 0:
            self._items.add(item)
        self._counter[item] += 1
        
        def undo():
            """Decrements the item's reference count and removes it from the set if the count reaches zero."""
            self._counter[item] -= 1
            if self._counter[item] == 0:
                self._items.discard(item) # Use discard for safe removal
                del self._counter[item]
        return undo

    def result(self):
        """Returns a copy of the resulting set."""
        return self._items.copy()

    def is_empty(self):
        """Checks if the collection is empty."""
        return not self._items
