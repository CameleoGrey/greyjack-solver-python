# greynet/collectors/variance_collector.py
from __future__ import annotations
from .base_collector import BaseCollector
import math

class VarianceCollector(BaseCollector):
    """
    A collector that calculates the population variance for a group of items
    based on a numeric mapping function.
    """
    def __init__(self, mapping_function):
        self._mapping_function = mapping_function
        self._sum = 0.0
        self._sum_sq = 0.0  # Sum of squares
        self._count = 0

    def insert(self, item):
        """Adds a value to the calculation."""
        value = float(self._mapping_function.apply(item))
        self._sum += value
        self._sum_sq += value ** 2
        self._count += 1
        def undo():
            self._sum -= value
            self._sum_sq -= value ** 2
            self._count -= 1
        return undo

    def result(self):
        """Returns the calculated population variance."""
        if self._count < 2:
            return 0.0

        mean = self._sum / self._count
        # Population variance formula: E[X^2] - (E[X])^2
        variance = (self._sum_sq / self._count) - (mean ** 2)

        # Clamp variance at 0 to avoid domain errors from floating-point inaccuracies.
        return max(0, variance)

    def is_empty(self):
        """Checks if any items have been collected."""
        return self._count == 0
