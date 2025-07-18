
# greynet/nodes/sequence_pattern_node.py

from __future__ import annotations
import bisect
from collections import defaultdict
from datetime import datetime
from typing import Callable, Any, List

from ..nodes.abstract_node import AbstractNode
from ..core.tuple import UniTuple, TupleState, AbstractTuple
from ..core.tuple_pool import TuplePool
from ..collectors.temporal_collectors import EventSequencePattern

class SequencePatternNode(AbstractNode):
    """
    A node that correctly detects sequences of facts matching a defined pattern.
    
    This version contains a corrected algorithm for sequence detection that properly
    handles event insertion and retraction by rescanning for all valid sequences
    and reconciling the engine's state.
    """
    def __init__(self, node_id: int, pattern: EventSequencePattern,
                 time_extractor: Callable[[Any], datetime], scheduler, tuple_pool: TuplePool):
        super().__init__(node_id)
        self._pattern = pattern
        self._time_extractor = time_extractor
        self._scheduler = scheduler
        self._tuple_pool = tuple_pool

        # State Management
        # A sorted list of all events (facts) that could be part of a sequence.
        self._events: List[tuple[datetime, AbstractTuple]] = []
        # Tracks active sequences to manage propagation and retraction.
        # Key: frozenset of parent tuple IDs. Value: The propagated child tuple.
        self._active_sequences: dict[frozenset[int], UniTuple] = {}

    def insert(self, parent_tuple: AbstractTuple):
        """Inserts a fact, adds it to the event timeline, and re-evaluates sequences."""
        timestamp = self._time_extractor(parent_tuple.fact_a)
        event_entry = (timestamp, parent_tuple)
        
        # Insert event while maintaining chronological order.
        bisect.insort_left(self._events, event_entry)
        self._rescan_and_reconcile()

    def retract(self, parent_tuple: AbstractTuple):
        """Retracts a fact, removes it from the timeline, and re-evaluates sequences."""
        timestamp = self._time_extractor(parent_tuple.fact_a)
        event_entry = (timestamp, parent_tuple)

        try:
            self._events.remove(event_entry)
            self._rescan_and_reconcile()
        except ValueError:
            # Fact was not in the event list, nothing to do.
            return

    def _rescan_and_reconcile(self):
        """
        Scans for all currently valid sequences and reconciles the engine state
        by propagating new sequences and retracting those that are no longer valid.
        """
        all_found_sequences = self._find_all_valid_sequences()
        
        current_keys = set(self._active_sequences.keys())
        found_keys = set(all_found_sequences.keys())

        # Retract sequences that were active but are no longer valid.
        for key in current_keys - found_keys:
            child_tuple = self._active_sequences.pop(key)
            self._retract_child(child_tuple)

        # Propagate new valid sequences that were not previously active.
        for key in found_keys - current_keys:
            parent_tuples = all_found_sequences[key]
            child_tuple = self._propagate_new_sequence(parent_tuples)
            self._active_sequences[key] = child_tuple

    def _find_all_valid_sequences(self) -> dict[frozenset[int], List[AbstractTuple]]:
        """
        Finds all unique, complete sequences that match the pattern from the current event list.
        """
        found_sequences = {}
        
        # Iterate through all events, treating each as a potential start of a sequence.
        for i, (start_time, start_tuple) in enumerate(self._events):
            # The event must match the first step of the pattern.
            if self._pattern.pattern_steps[0](start_tuple.fact_a):
                # Find all possible complete sequences starting from this event.
                initial_sequence = [start_tuple]
                complete_sequences = self._find_sequence_completions(
                    current_sequence=initial_sequence,
                    search_from_index=i + 1,
                    sequence_start_time=start_time
                )
                
                for sequence in complete_sequences:
                    # Use a key based on the object IDs of the facts to uniquely
                    # identify this specific instance of a sequence.
                    key = frozenset(t.greynet_fact_id for t in sequence)
                    if key not in found_sequences:
                        found_sequences[key] = sequence
                        
        return found_sequences

    def _find_sequence_completions(self, current_sequence: List[AbstractTuple], 
                                   search_from_index: int, 
                                   sequence_start_time: datetime) -> List[List[AbstractTuple]]:
        """
        A robust recursive function to find all valid completions of a partial sequence.
        """
        # Base case: The sequence has the required number of steps. It's a valid completion.
        if len(current_sequence) == len(self._pattern.pattern_steps):
            return [current_sequence]
        
        next_step_index = len(current_sequence)
        next_predicate = self._pattern.pattern_steps[next_step_index]
        all_completions = []
        
        # Iterate through subsequent events to find a match for the next step.
        for i in range(search_from_index, len(self._events)):
            event_time, event_tuple = self._events[i]
            
            # Optimization: Stop searching if the event is outside the pattern's time window.
            if event_time - sequence_start_time > self._pattern.within:
                break
            
            # Check if this event matches the predicate for the next step in the pattern.
            if next_predicate(event_tuple.fact_a):
                # We found a potential next event.
                extended_sequence = current_sequence + [event_tuple]
                
                # Recursively find the rest of the sequence, starting from the event AFTER this one.
                completions = self._find_sequence_completions(
                    extended_sequence,
                    i + 1,
                    sequence_start_time
                )
                all_completions.extend(completions)
                
                # If gaps are not allowed, we MUST use this first match we found.
                # We cannot continue searching for other candidates for this same step.
                if not self._pattern.allow_gaps:
                    break 
        
        return all_completions

    def _propagate_new_sequence(self, parent_tuples: List[AbstractTuple]) -> UniTuple:
        """Creates and schedules a new child tuple representing a valid sequence."""
        # The fact of the child tuple is the list of facts from the sequence.
        sequence_facts = [p.fact_a for p in parent_tuples]
        child_tuple = self._tuple_pool.acquire(UniTuple, fact_a=sequence_facts)
        child_tuple.node, child_tuple.state = self, TupleState.CREATING
        self._scheduler.schedule(child_tuple)
        return child_tuple

    def _retract_child(self, child_tuple: UniTuple):
        """Schedules a child tuple for retraction if it's no longer valid."""
        if child_tuple.state == TupleState.CREATING:
            child_tuple.state = TupleState.ABORTING
        elif not child_tuple.state.is_dirty():
            child_tuple.state = TupleState.DYING
            self._scheduler.schedule(child_tuple)
