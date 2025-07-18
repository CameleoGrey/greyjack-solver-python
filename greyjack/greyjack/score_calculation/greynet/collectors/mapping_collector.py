# greynet/collectors/mapping_collector.py
from __future__ import annotations
from .base_collector import BaseCollector
from ..function import Function
from typing import Callable

class MappingCollector(BaseCollector):
    """
    A collector that first applies a mapping function to each item before
    passing it to a downstream collector for aggregation.
    """
    def __init__(self, mapping_function: Callable, downstream_supplier: Callable):
        if not isinstance(mapping_function, Function):
            class Wrapper(Function):
                def apply(self, value): return mapping_function(value)
            self._mapping_function = Wrapper()
        else:
            self._mapping_function = mapping_function
        self._downstream = downstream_supplier()

    def insert(self, item):
        """Applies the mapping function and inserts the result into the downstream collector."""
        mapped_item = self._mapping_function.apply(item)
        return self._downstream.insert(mapped_item)

    def result(self):
        """Returns the result from the downstream collector."""
        return self._downstream.result()

    def is_empty(self):
        """Checks if the downstream collector is empty."""
        return self._downstream.is_empty()
