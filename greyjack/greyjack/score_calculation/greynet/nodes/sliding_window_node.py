# greynet/nodes/sliding_window_node.py

from __future__ import annotations
import bisect
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .abstract_node import AbstractNode
from ..core.tuple import BiTuple, TupleState, AbstractTuple
from ..core.tuple_pool import TuplePool

class SlidingWindowNode(AbstractNode):
    """
    A node that groups facts into sliding time windows.

    For each window, it emits a BiTuple where:
    - fact_a: The start datetime of the window.
    - fact_b: A list of all facts that fall within that window.

    The node correctly handles insertion and retraction of facts, updating
    the corresponding window tuples as needed.
    """
    def __init__(self, node_id: int, time_extractor: callable, window_size: timedelta, 
                 slide_interval: timedelta, scheduler, tuple_pool: TuplePool):
        super().__init__(node_id)
        self._time_extractor = time_extractor
        self._window_size = window_size
        self._slide_interval = slide_interval
        self._scheduler = scheduler
        self._tuple_pool = tuple_pool

        # State management
        self._events: list[tuple[datetime, AbstractTuple]] = []
        self._fact_to_windows = defaultdict(set) # Maps fact.id -> {window_start_ts, ...}
        self._active_windows = {} # Maps window_start_ts -> emitted_BiTuple

        # Use a fixed epoch for reproducible window alignment
        self._epoch_start_ts = datetime(1970, 1, 1, tzinfo=timezone.utc).timestamp()
        self._slide_sec = self._slide_interval.total_seconds()
        self._window_sec = self._window_size.total_seconds()

    def _get_windows_for_timestamp(self, ts: datetime) -> list[datetime]:
        """Calculates all sliding windows a given timestamp falls into."""
        ts_seconds = ts.timestamp()
        # First possible window starts such that its end (start + size) includes the timestamp
        first_window_start_idx = (ts_seconds - self._window_sec) / self._slide_sec
        # Last possible window starts such that its start is before or at the timestamp
        last_window_start_idx = ts_seconds / self._slide_sec
        
        windows = []
        # Iterate through all possible window start indices
        for i in range(int(first_window_start_idx) + 1, int(last_window_start_idx) + 1):
             start_ts = self._epoch_start_ts + i * self._slide_sec
             windows.append(datetime.fromtimestamp(start_ts, tz=timezone.utc))
        return windows

    def insert(self, tuple_):
        fact = tuple_.fact_a
        fact_id = fact.id
        timestamp = self._time_extractor(fact)

        # Maintain a sorted list of events
        event_entry = (timestamp, fact)
        bisect.insort(self._events, event_entry)

        affected_windows = self._get_windows_for_timestamp(timestamp)
        for window_start in affected_windows:
            self._fact_to_windows[fact_id].add(window_start)
            self._update_window(window_start)

    def retract(self, tuple_):
        fact = tuple_.fact_a
        fact_id = fact.id
        timestamp = self._time_extractor(fact)

        event_entry = (timestamp, fact)
        try:
            # O(N) removal, can be optimized if needed
            self._events.remove(event_entry) 
        except ValueError:
            return # Fact was not present

        # Update all windows this fact was part of
        if fact_id in self._fact_to_windows:
            affected_windows = self._fact_to_windows.pop(fact_id)
            for window_start in affected_windows:
                self._update_window(window_start)

    def _update_window(self, window_start: datetime):
        """(Re)calculates and propagates a single window."""
        window_end = window_start + self._window_size
        
        # Find all facts within this window's time range from the sorted list
        start_idx = bisect.bisect_left(self._events, (window_start, None))
        end_idx = bisect.bisect_right(self._events, (window_end, None))
        
        facts_in_window = [fact for ts, fact in self._events[start_idx:end_idx]]

        # Retract the old tuple for this window if it exists
        if window_start in self._active_windows:
            old_tuple = self._active_windows.pop(window_start)
            self._retract_child(old_tuple)

        # If there are facts, create and propagate a new tuple
        if facts_in_window:
            new_tuple = self._create_child(window_start, facts_in_window)
            self._active_windows[window_start] = new_tuple

    def _create_child(self, key: datetime, result: list) -> BiTuple:
        tuple_ = self._tuple_pool.acquire(BiTuple, fact_a=key, fact_b=result)
        tuple_.node, tuple_.state = self, TupleState.CREATING
        self._scheduler.schedule(tuple_)
        return tuple_

    def _retract_child(self, tuple_: BiTuple):
        if tuple_.state == TupleState.CREATING:
            tuple_.state = TupleState.ABORTING
        elif not tuple_.state.is_dirty():
            tuple_.state = TupleState.DYING
            self._scheduler.schedule(tuple_)
