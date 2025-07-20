# greynet/common/joiner_type.py
from enum import Enum

class JoinerType(Enum):
    EQUAL = "equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    NOT_EQUAL = "not_equal"
    RANGE_OVERLAPS = "range_overlaps"
    RANGE_CONTAINS = "range_contains"
    RANGE_WITHIN = "range_within"

    def create_comparator(self):
        comparators = {
            JoinerType.EQUAL: lambda a, b: a == b,
            JoinerType.LESS_THAN: lambda a, b: a < b,
            JoinerType.LESS_THAN_OR_EQUAL: lambda a, b: a <= b,
            JoinerType.GREATER_THAN: lambda a, b: a > b,
            JoinerType.GREATER_THAN_OR_EQUAL: lambda a, b: a >= b,
            JoinerType.NOT_EQUAL: lambda a, b: a != b,
            JoinerType.RANGE_OVERLAPS: self._range_overlaps,
            JoinerType.RANGE_CONTAINS: self._range_contains,
            JoinerType.RANGE_WITHIN: self._range_within,
        }
        return comparators[self]

    @staticmethod
    def _validate_range(val, name="range"):
        if not isinstance(val, (list, tuple)) or len(val) != 2:
            raise TypeError(f"{name} must be a tuple or list of length 2, representing [start, end]")

    @staticmethod
    def _range_overlaps(range_a, range_b):
        JoinerType._validate_range(range_a, "range_a")
        JoinerType._validate_range(range_b, "range_b")
        return not (range_a[1] < range_b[0] or range_b[1] < range_a[0])

    @staticmethod
    def _range_contains(container_range, content_range):
        JoinerType._validate_range(container_range, "container_range")
        JoinerType._validate_range(content_range, "content_range")
        return container_range[0] <= content_range[0] and content_range[1] <= container_range[1]

    @staticmethod
    def _range_within(content_range, container_range):
        return JoinerType._range_contains(container_range, content_range)