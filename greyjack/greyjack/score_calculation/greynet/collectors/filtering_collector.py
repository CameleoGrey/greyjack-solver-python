# greynet/collectors/filtering_collector.py
from __future__ import annotations
from .base_collector import BaseCollector
from ..function import Predicate
from typing import Callable

class FilteringCollector(BaseCollector):
    """
    A collector that filters items based on a predicate before passing them
    to a downstream collector for aggregation.
    """
    def __init__(self, predicate: Callable, downstream_supplier: Callable):
        if not isinstance(predicate, Predicate):
            class Wrapper(Predicate):
                def test(self, value): return predicate(value)
            self._predicate = Wrapper()
        else:
            self._predicate = predicate
        self._downstream = downstream_supplier()

    def insert(self, item):
        """If the item passes the predicate, insert it into the downstream collector."""
        if self._predicate.test(item):
            return self._downstream.insert(item)
        else:
            # Return a no-op undo function if the item is filtered out.
            return lambda: None

    def result(self):
        """Returns the result from the downstream collector."""
        return self._downstream.result()

    def is_empty(self):
        """Checks if the downstream collector is empty."""
        return self._downstream.is_empty()
