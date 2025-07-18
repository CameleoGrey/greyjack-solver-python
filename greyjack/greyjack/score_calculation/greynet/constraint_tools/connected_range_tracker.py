
# greynet/constraint_tools/connected_range_tracker.py

from dataclasses import dataclass
from typing import Any, List

@dataclass(order=True)
class ConnectedRange:
    start: Any
    end: Any
    data: List[Any]

    def can_connect(self, other):
        # Ranges connect if they overlap or are immediately adjacent.
        return not (self.end < other.start or other.end < self.start)

    def merge(self, other):
        return ConnectedRange(
            start=min(self.start, other.start),
            end=max(self.end, other.end),
            data=self.data + other.data
        )

class ConnectedRangeTracker:
    def __init__(self, start_mapping, end_mapping):
        self._start_mapping = start_mapping
        self._end_mapping = end_mapping
        self._ranges = []
        self._item_to_range = {}

    def add(self, item):
        start, end = self._start_mapping(item), self._end_mapping(item)
        new_range = ConnectedRange(start=start, end=end, data=[item])

        overlapping, remaining = [], []
        for r in self._ranges:
            if new_range.can_connect(r):
                overlapping.append(r)
            else:
                remaining.append(r)

        merged = new_range
        for r in overlapping:
            merged = merged.merge(r)

        self._ranges = remaining # Temporarily remove merged ranges
        self._insert_sorted(merged) # Add the new merged range

        # Update the item-to-range mapping for all items in the new range
        for item_in_merged in merged.data:
            self._item_to_range[item_in_merged] = merged

    def remove(self, item):
        if item not in self._item_to_range:
            return

        containing_range = self._item_to_range.pop(item)
        self._ranges.remove(containing_range)

        remaining_items = [i for i in containing_range.data if i != item]
        if not remaining_items:
            return

        # Rebuild ranges from the remaining items, as the removal might
        # have split a single continuous range into two or more.
        new_ranges = self._rebuild_ranges(remaining_items)
        for r in new_ranges:
            self._insert_sorted(r)
            for i in r.data:
                self._item_to_range[i] = r

    def get_connected_ranges(self):
        return self._ranges.copy()

    def _insert_sorted(self, range_):
        import bisect
        bisect.insort_left(self._ranges, range_, key=lambda r: r.start)

    def _rebuild_ranges(self, items):
        if not items:
            return []
        # Sort items by their start time to reconstruct ranges efficiently
        sorted_items = sorted(items, key=self._start_mapping)

        rebuilt_ranges = []
        current_range = ConnectedRange(
            self._start_mapping(sorted_items[0]),
            self._end_mapping(sorted_items[0]),
            [sorted_items[0]]
        )

        for item in sorted_items[1:]:
            item_range = ConnectedRange(
                self._start_mapping(item),
                self._end_mapping(item),
                [item]
            )
            if current_range.can_connect(item_range):
                current_range = current_range.merge(item_range)
            else:
                rebuilt_ranges.append(current_range)
                current_range = item_range

        rebuilt_ranges.append(current_range)
        return rebuilt_ranges
