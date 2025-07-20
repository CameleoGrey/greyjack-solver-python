# greynet/collectors/constraint_match_collector.py
from __future__ import annotations
from .list_collector import ListCollector

class ConstraintMatchCollector(ListCollector):
    """
    A collector for tracking the specific facts that constitute a constraint match
    within a group. It is functionally equivalent to a ListCollector but provides
    semantic clarity in rule definitions.

    Note: The primary mechanism for tracking all constraint matches across the
    entire session is the `session.get_constraint_matches()` method, which
    inspects the internal state of the engine's ScoringNodes.
    """
    pass
