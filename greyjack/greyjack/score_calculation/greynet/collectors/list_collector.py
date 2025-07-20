# greynet/collectors/list_collector.py
from ..collectors.base_collector import BaseCollector

class ListCollector(BaseCollector):
    def __init__(self):
        self._items = []

    def insert(self, item):
        self._items.append(item)
        def undo():
            # Removing the specific item instance is crucial for correctness,
            # especially if duplicate items can exist.
            try:
                self._items.remove(item)
            except ValueError:
                # This can happen in complex scenarios if an item is retracted
                # more than once; it's safe to ignore.
                pass
        return undo

    def result(self):
        # Return a copy to prevent external mutations from affecting the
        # internal state of the collector.
        return self._items.copy()

    def is_empty(self):
        return not self._items