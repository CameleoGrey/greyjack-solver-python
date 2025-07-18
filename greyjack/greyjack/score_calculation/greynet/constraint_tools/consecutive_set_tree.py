
# greynet/constraint_tools/consecutive_set_tree.py

from dataclasses import dataclass
from typing import Any, Tuple

@dataclass(frozen=True, order=True)
class ConsecutiveSequence:
    """Represents a continuous sequence of items."""
    start: Any
    end: Any
    length: int
    items: Tuple[Any, ...]

class ConsecutiveSetTree:
    """
    A data structure for efficiently tracking consecutive sequences of items.
    """
    def __init__(self, sequence_function, increment_function):
        self._sequence_func = sequence_function
        self._inc_func = increment_function
        self._item_to_pos = {}
        self._pos_to_seq = {}
        self._sequences = set()

    def add(self, item):
        """Adds an item and updates the sequences accordingly."""
        if item in self._item_to_pos:
            return

        pos = self._sequence_func(item)
        self._item_to_pos[item] = pos

        prev_pos = self._inc_func(pos, -1)
        next_pos = self._inc_func(pos, 1)
        
        prev_seq = self._pos_to_seq.get(prev_pos)
        next_seq = self._pos_to_seq.get(next_pos)

        if prev_seq and next_seq:
            if prev_seq is not next_seq:
                self._merge(prev_seq, next_seq, item, pos)
        elif prev_seq:
            self._extend(prev_seq, item, pos)
        elif next_seq:
            self._prepend(next_seq, item, pos)
        else:
            self._create(item, pos)

    def remove(self, item):
        """
        Robustly removes an item by finding its sequence, tearing it down,
        and rebuilding new sequences from the remaining items. This approach
        correctly handles cases where a sequence is split in two.
        """
        if item not in self._item_to_pos:
            return

        pos = self._item_to_pos[item]  # Get position without popping
        seq = self._pos_to_seq.get(pos)

        if not seq:
            # The item was mapped but not part of a sequence. Just clean up its own mappings.
            del self._item_to_pos[item]
            if self._pos_to_seq.get(pos) is None:
                 del self._pos_to_seq[pos]
            return

        # 1. Identify which items we need to re-add later.
        items_to_re_add = [i for i in seq.items if i is not item]

        # 2. Completely remove the old sequence and all its associated mappings
        #    to ensure a clean state before rebuilding.
        self._sequences.discard(seq)
        for i in seq.items:
            if i in self._item_to_pos:
                item_pos = self._item_to_pos.pop(i)
                if self._pos_to_seq.get(item_pos) is seq:
                    del self._pos_to_seq[item_pos]
        
        # Clean boundary pointers as a safeguard.
        if self._pos_to_seq.get(seq.start) is seq:
            del self._pos_to_seq[seq.start]
        if self._pos_to_seq.get(seq.end) is seq:
            del self._pos_to_seq[seq.end]

        # 3. Re-add the remaining items. The `add` method will correctly form
        #    new sequences (e.g., splitting the old one into two).
        for i in items_to_re_add:
            self.add(i)

    def _update_mappings(self, seq):
        """Updates internal dictionaries to map positions to the new sequence."""
        for item in seq.items:
            pos = self._item_to_pos.get(item)
            if pos is not None:
                self._pos_to_seq[pos] = seq
        self._pos_to_seq[seq.start] = seq
        self._pos_to_seq[seq.end] = seq

    def _create(self, item, pos):
        """Creates a new sequence of length 1."""
        seq = ConsecutiveSequence(start=pos, end=pos, length=1, items=(item,))
        self._sequences.add(seq)
        self._update_mappings(seq)

    def _extend(self, seq, item, pos):
        """Adds an item to the end of an existing sequence."""
        self._sequences.remove(seq)
        new_items = seq.items + (item,)
        new_seq = ConsecutiveSequence(start=seq.start, end=pos, length=len(new_items), items=new_items)
        self._sequences.add(new_seq)
        self._update_mappings(new_seq)

    def _prepend(self, seq, item, pos):
        """Adds an item to the beginning of an existing sequence."""
        self._sequences.remove(seq)
        new_items = (item,) + seq.items
        new_seq = ConsecutiveSequence(start=pos, end=seq.end, length=len(new_items), items=new_items)
        self._sequences.add(new_seq)
        self._update_mappings(new_seq)

    def _merge(self, prev_seq, next_seq, item, pos):
        """Merges two sequences with a new item in between."""
        self._sequences.remove(prev_seq)
        self._sequences.remove(next_seq)
        new_items = prev_seq.items + (item,) + next_seq.items
        new_seq = ConsecutiveSequence(start=prev_seq.start, end=next_seq.end, length=len(new_items), items=new_items)
        self._sequences.add(new_seq)
        self._update_mappings(new_seq)

    def get_sequences(self):
        """Returns the current list of all consecutive sequences."""
        return list(self._sequences)
