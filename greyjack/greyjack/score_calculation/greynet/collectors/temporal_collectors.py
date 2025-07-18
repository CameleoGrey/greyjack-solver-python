from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
# --- Start of Bug Fix ---
from typing import Dict, List, Callable, Optional, Any, Tuple
# --- End of Bug Fix ---
from dataclasses import dataclass
from typing import Optional
from enum import Enum
import bisect

# TODO: Fix temporal, sequential features
# TODO: Add debug, tracing for temporal, sequential features

class WindowType(Enum):
    TUMBLING = "tumbling"    # Non-overlapping fixed windows
    SLIDING = "sliding"      # Overlapping windows that slide
    SESSION = "session"      # Dynamic windows based on activity gaps
    HOPPING = "hopping"      # Fixed-size windows with custom hop interval

@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime
    window_type: WindowType
    
    def contains(self, timestamp: datetime) -> bool:
        return self.start <= timestamp < self.end
    
    def overlaps(self, other: 'TimeWindow') -> bool:
        return not (self.end <= other.start or other.end <= self.start)
    
    def duration(self) -> timedelta:
        return self.end - self.start
    
    @classmethod
    def tumbling(cls, start: datetime, duration: timedelta) -> 'TimeWindow':
        return cls(start, start + duration, WindowType.TUMBLING)
    
    @classmethod
    def sliding(cls, start: datetime, duration: timedelta) -> 'TimeWindow':
        return cls(start, start + duration, WindowType.SLIDING)

@dataclass
class TemporalEvent:
    """Wrapper for facts with temporal information"""
    fact: Any
    timestamp: datetime
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.event_id is None:
            self.event_id = f"evt_{self.fact.greynet_fact_id}_{self.timestamp.timestamp()}"

# --- Start of Bug Fix ---
@dataclass()
class EventSequencePattern:
    """
    ENHANCED: Improved pattern definition with better validation.
    """
    pattern_steps: Tuple[Callable[[Any], bool], ...]
    within: timedelta
    allow_gaps: bool = True
# --- End of Bug Fix ---
    
    def __post_init__(self):
        """Validate pattern configuration."""
        if not self.pattern_steps:
            raise ValueError("Pattern must have at least one step")
        
        if len(self.pattern_steps) < 2:
            raise ValueError("Pattern must have at least two steps to form a sequence")
        
        if self.within.total_seconds() <= 0:
            raise ValueError("Time window must be positive")
        
        # Validate that all steps are callable
        for i, step in enumerate(self.pattern_steps):
            if not callable(step):
                raise ValueError(f"Pattern step {i} must be callable")

    def matches_sequence(self, facts: List[Any], timestamps: List[datetime]) -> bool:
        """
        ENHANCED: Validates that a sequence of facts matches this pattern.
        """
        if len(facts) != len(self.pattern_steps):
            return False
        
        if len(facts) != len(timestamps):
            return False
        
        # Check time window constraint
        if timestamps[-1] - timestamps[0] > self.within:
            return False
        
        # Check each step matches
        for i, (fact, predicate) in enumerate(zip(facts, self.pattern_steps)):
            if not predicate(fact):
                return False
        
        # Check temporal ordering (timestamps should be non-decreasing)
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i-1]:
                return False
        
        # If gaps are not allowed, check for strict temporal adjacency
        if not self.allow_gaps:
            # This would require domain-specific logic to determine
            # what constitutes "adjacent" events
            pass
        
        return True

class TemporalCollector:
    """Base class for temporal aggregation collectors"""
    
    def __init__(self, time_extractor: Callable[[Any], datetime]):
        self.time_extractor = time_extractor
        self.events: List[TemporalEvent] = []
        
    def insert(self, item: Any):
        timestamp = self.time_extractor(item)
        event = TemporalEvent(item, timestamp)
        
        insert_pos = bisect.bisect_left(self.events, event.timestamp, key=lambda e: e.timestamp)
        self.events.insert(insert_pos, event)
        
        def undo():
            try:
                self.events.remove(event)
            except ValueError:
                pass
        return undo

    def get_events_in_window(self, window: TimeWindow) -> List[Any]:
        start_idx = bisect.bisect_left(self.events, window.start, key=lambda e: e.timestamp)
        end_idx = bisect.bisect_right(self.events, window.end, key=lambda e: e.timestamp)
        return [e.fact for e in self.events[start_idx:end_idx]]

class TumblingWindowCollector(TemporalCollector):
    """Collector that creates non-overlapping tumbling windows"""
    
    def __init__(self, 
                 time_extractor: Callable[[Any], datetime],
                 window_size: timedelta,
                 window_start: Optional[datetime] = None):
        super().__init__(time_extractor)
        self.window_size = window_size
        
        if window_start:
            self.window_start_epoch = window_start.timestamp()
        else:
            self.window_start_epoch = datetime(1970, 1, 1, tzinfo=timezone.utc).timestamp()
        
        self._windows: Dict[int, List[Any]] = defaultdict(list)
        
    def _get_window_key(self, timestamp: datetime) -> int:
        elapsed = timestamp.timestamp() - self.window_start_epoch
        window_size_sec = self.window_size.total_seconds()
        window_index = int(elapsed // window_size_sec)
        return int(self.window_start_epoch + window_index * window_size_sec)

    def insert(self, item: Any):
        undo_super = super().insert(item)
        self._rebuild_windows()
        def undo():
            undo_super()
            self._rebuild_windows()
        return undo

    def _rebuild_windows(self):
        self._windows.clear()
        for event in self.events:
            window_key = self._get_window_key(event.timestamp)
            self._windows[window_key].append(event.fact)

    def result(self) -> Dict[datetime, List[Any]]:
        return {datetime.fromtimestamp(k, tz=timezone.utc): v for k, v in self._windows.items()}
    
    def is_empty(self) -> bool:
        return not self.events
