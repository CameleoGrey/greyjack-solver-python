# greynet/collectors/distinct_collector.py
from __future__ import annotations
from collections import Counter
from .base_collector import BaseCollector

class DistinctCollector(BaseCollector):
    """
    A collector that aggregates unique items into a list, preserving insertion order.
    It correctly handles the insertion and retraction of duplicate items.
    """
    def __init__(self):
        self._items = {}  # Using a dict as an ordered set
        self._counter = Counter()

    def insert(self, item):
        """Adds an item if it's not already present and tracks its reference count."""
        if self._counter[item] == 0:
            self._items[item] = None # Add to the ordered set
        self._counter[item] += 1
        
        def undo():
            """Decrements the item's reference count and removes it if the count reaches zero."""
            self._counter[item] -= 1
            if self._counter[item] == 0:
                self._items.pop(item, None)
                del self._counter[item]
        return undo

    def result(self):
        """Returns a list of the unique items in their insertion order."""
        return list(self._items.keys())

    def is_empty(self):
        """Checks if the collection is empty."""
        return not self._items
