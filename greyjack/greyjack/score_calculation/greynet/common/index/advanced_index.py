
# greynet/common/index/advanced_index.py

from __future__ import annotations
import bisect
from collections import defaultdict
from typing import List, Any

from ...common.joiner_type import JoinerType
from ...core.tuple import AbstractTuple
from ...constraint_tools.counting_bloom_filter import CountingBloomFilter

class AdvancedIndex:
    """
    An index that supports advanced join types, including range-based comparisons.
    - For EQUAL, it uses a hash map for O(1) average time complexity.
    - For NOT_EQUAL, it uses a hybrid strategy with a Counting Bloom Filter
      and a flat list of all tuples to optimize lookups.
    - For range comparisons (LESS_THAN, etc.), it maintains a sorted list.
    """
    def __init__(self, index_properties, joiner_type: JoinerType = JoinerType.EQUAL):
        self._index_properties = index_properties
        self._joiner_type = joiner_type
        
        # Select the appropriate data structure based on the joiner type
        if joiner_type == JoinerType.EQUAL:
            self._index_map = defaultdict(list)
        # --- Start of Modified Code ---
        elif joiner_type == JoinerType.NOT_EQUAL:
            # For NOT_EQUAL joins, we use a hybrid approach.
            # 1. A standard hash map to quickly find tuples TO EXCLUDE.
            self._index_map = defaultdict(list)
            # 2. A flat list of all tuples for faster full iteration than dict.keys().
            self._all_tuples: List[AbstractTuple] = []
            # 3. A Counting Bloom Filter for a fast probabilistic check.
            #    These values are defaults; could be made configurable.
            self._bloom_filter = CountingBloomFilter(estimated_items=1000, false_positive_rate=0.01)
        # --- End of Modified Code ---
        else:
            # Sorted list for efficient range scans
            self._sorted_entries: List[tuple[Any, List[AbstractTuple]]] = []
            self._keys_view: List[Any] = [] # A synchronized view of keys for bisect

    def put(self, tuple_: AbstractTuple):
        """Adds a tuple to the index."""
        key = self._index_properties.get_property(tuple_)
        # --- Start of Modified Code ---
        if self._joiner_type == JoinerType.NOT_EQUAL:
            self._index_map[key].append(tuple_)
            self._all_tuples.append(tuple_)
            # Add key to bloom filter only if it's the first time we see this key.
            if len(self._index_map[key]) == 1:
                self._bloom_filter.add(key)
        # --- End of Modified Code ---
        elif hasattr(self, '_index_map'):
            self._index_map[key].append(tuple_)
        else:
            # Find the insertion point in the sorted list
            idx = bisect.bisect_left(self._keys_view, key)
            
            # If a list of tuples already exists for this key, append to it
            if idx < len(self._keys_view) and self._keys_view[idx] == key:
                self._sorted_entries[idx][1].append(tuple_)
            else:
                # Otherwise, insert a new (key, [tuple]) entry
                self._sorted_entries.insert(idx, (key, [tuple_]))
                self._keys_view.insert(idx, key)

    def get_matches(self, query_key: Any) -> List[AbstractTuple]:
        """
        Retrieves all tuples that match the query_key according to the joiner type.
        """
        if hasattr(self, '_index_map'):
            if self._joiner_type == JoinerType.EQUAL:
                return self._index_map.get(query_key, [])
            
            # --- Start of Modified Code ---
            if self._joiner_type == JoinerType.NOT_EQUAL:
                # OPTIMIZATION 1: Use the Bloom filter for a fast path.
                # If the key is definitively not in the index, no tuples need to be
                # excluded, so we can return the entire list of tuples.
                if query_key not in self._bloom_filter:
                    return self._all_tuples.copy()

                # OPTIMIZATION 2: The key might be present.
                # We get the set of tuples to exclude. Using a set provides O(1)
                # average time complexity for the 'in' check below.
                tuples_to_exclude = set(self._index_map.get(query_key, []))

                # If the Bloom filter had a false positive, the exclusion set will be empty.
                if not tuples_to_exclude:
                    return self._all_tuples.copy()
                
                # Perform the full exclusion. This is still O(N), but iterating a list
                # is generally faster than iterating dictionary items/keys.
                return [t for t in self._all_tuples if t not in tuples_to_exclude]
            # --- End of Modified Code ---
        else:
            # --- Start of Enhancement ---
            # Use bisect for efficient O(log N) lookups on the sorted list
            if self._joiner_type == JoinerType.LESS_THAN:
                # Find index of first element >= query_key
                end_idx = bisect.bisect_left(self._keys_view, query_key)
                target_slice = self._sorted_entries[:end_idx]
            elif self._joiner_type == JoinerType.LESS_THAN_OR_EQUAL:
                # Find index of first element > query_key
                end_idx = bisect.bisect_right(self._keys_view, query_key)
                target_slice = self._sorted_entries[:end_idx]
            elif self._joiner_type == JoinerType.GREATER_THAN:
                # Find index of first element > query_key
                start_idx = bisect.bisect_right(self._keys_view, query_key)
                target_slice = self._sorted_entries[start_idx:]
            elif self._joiner_type == JoinerType.GREATER_THAN_OR_EQUAL:
                # Find index of first element >= query_key
                start_idx = bisect.bisect_left(self._keys_view, query_key)
                target_slice = self._sorted_entries[start_idx:]
            else:
                # Fallback for any other custom comparators, though less efficient.
                # The primary range joins are now optimized.
                comparator = self._joiner_type.create_comparator()
                target_slice = [
                    entry for entry in self._sorted_entries 
                    if comparator(entry[0], query_key)
                ]

            # Flatten the list of lists of tuples into a single list of tuples
            return [
                tuple_ for _, tuple_list in target_slice for tuple_ in tuple_list
            ]
            # --- End of Enhancement ---

    def remove(self, tuple_: AbstractTuple):
        """Removes a tuple from the index."""
        key = self._index_properties.get_property(tuple_)
        # --- Start of Modified Code ---
        if self._joiner_type == JoinerType.NOT_EQUAL:
            if key in self._index_map:
                try:
                    self._index_map[key].remove(tuple_)
                    # This is O(N) and a clear performance trade-off for this strategy.
                    self._all_tuples.remove(tuple_)
                    
                    # If the key is no longer associated with any tuples,
                    # remove it from the map and the Bloom filter.
                    if not self._index_map[key]:
                        del self._index_map[key]
                        self._bloom_filter.remove(key)
                except ValueError:
                    pass # Tuple was already removed.
        # --- End of Modified Code ---
        elif hasattr(self, '_index_map'):
            if key in self._index_map:
                try:
                    self._index_map[key].remove(tuple_)
                    if not self._index_map[key]:
                        del self._index_map[key]
                except ValueError:
                    # Tuple was already removed or never existed, ignore.
                    pass
        else:
            # Find the entry using binary search
            idx = bisect.bisect_left(self._keys_view, key)
            if idx < len(self._keys_view) and self._keys_view[idx] == key:
                try:
                    tuples = self._sorted_entries[idx][1]
                    tuples.remove(tuple_)
                    # If the list for this key is now empty, remove the key itself
                    if not tuples:
                        self._sorted_entries.pop(idx)
                        self._keys_view.pop(idx)
                except ValueError:
                    # Tuple was already removed, ignore.
                    pass
