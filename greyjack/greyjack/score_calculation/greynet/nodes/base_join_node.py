# greynet/nodes/base_join_node.py
from __future__ import annotations
from abc import ABC, abstractmethod

from greyjack.score_calculation.greynet.nodes.abstract_node import AbstractNode
from greyjack.score_calculation.greynet.common.index.uni_index import UniIndex
from greyjack.score_calculation.greynet.common.index.advanced_index import AdvancedIndex
from greyjack.score_calculation.greynet.core.tuple import TupleState, AbstractTuple
from greyjack.score_calculation.greynet.common.joiner_type import JoinerType

class BaseJoinNode(AbstractNode, ABC):
    """
    An abstract base class for all join nodes (Bi, Tri, Quad, etc.).
    It contains the common logic for indexing, matching, and propagating tuples,
    following the DRY principle. Subclasses only need to implement the
    creation of the specific child tuple.
    """
    def __init__(self, node_id, joiner_type, left_index_properties, right_index_properties, scheduler, tuple_pool):
        super().__init__(node_id)
        self.scheduler = scheduler
        self.tuple_pair_map = {}
        self.left_index = self._create_index(left_index_properties, joiner_type)
        self.right_index = self._create_index(right_index_properties, joiner_type)
        self.tuple_pool = tuple_pool 

    def _create_index(self, props, joiner):
        """Factory method to create the appropriate index based on joiner type."""
        if joiner == JoinerType.EQUAL:
            return UniIndex(props)
        return AdvancedIndex(props, joiner)

    # --- Abstract Method ---
    @abstractmethod
    def _create_child_tuple(self, left_tuple: AbstractTuple, right_tuple: AbstractTuple) -> AbstractTuple:
        """
        Abstract method to be implemented by subclasses.
        It must create and return the correct type of child tuple (e.g., BiTuple, TriTuple).
        """
        pass

    # --- Common Insertion Logic ---
    def insert_left(self, left_tuple: AbstractTuple):
        """Handles insertion from the left source stream."""
        self.left_index.put(left_tuple)
        key = self.left_index._index_properties.get_property(left_tuple)
        right_matches = self.right_index.get_matches(key) if hasattr(self.right_index, 'get_matches') else self.right_index.get(key)
        for right_tuple in right_matches:
            self.create_and_schedule_child(left_tuple, right_tuple)

    def insert_right(self, right_tuple: AbstractTuple):
        """Handles insertion from the right source stream."""
        self.right_index.put(right_tuple)
        key = self.right_index._index_properties.get_property(right_tuple)
        left_matches = self.left_index.get_matches(key) if hasattr(self.left_index, 'get_matches') else self.left_index.get(key)
        for left_tuple in left_matches:
            self.create_and_schedule_child(left_tuple, right_tuple)

    # --- Common Retraction Logic ---
    def retract_left(self, left_tuple: AbstractTuple):
        """Handles retraction from the left source stream."""
        self.left_index.remove(left_tuple)
        # Find all pairs involving the retracted left tuple
        pairs_to_remove = [p for p in self.tuple_pair_map if p[0] == left_tuple]
        for pair in pairs_to_remove:
            self.retract_and_schedule_child(pair[0], pair[1])

    def retract_right(self, right_tuple: AbstractTuple):
        """Handles retraction from the right source stream."""
        self.right_index.remove(right_tuple)
        # Find all pairs involving the retracted right tuple
        pairs_to_remove = [p for p in self.tuple_pair_map if p[1] == right_tuple]
        for pair in pairs_to_remove:
            self.retract_and_schedule_child(pair[0], pair[1])

    # --- Common Child Tuple Management ---
    def create_and_schedule_child(self, left_tuple: AbstractTuple, right_tuple: AbstractTuple):
        """Creates a child tuple using the abstract factory method and schedules it."""
        child = self._create_child_tuple(left_tuple, right_tuple)
        child.node, child.state = self, TupleState.CREATING
        self.tuple_pair_map[(left_tuple, right_tuple)] = child
        self.scheduler.schedule(child)

    def retract_and_schedule_child(self, left: AbstractTuple, right: AbstractTuple):
        """Removes a child tuple from the map and schedules its retraction."""
        child = self.tuple_pair_map.pop((left, right), None)
        if child:
            if child.state == TupleState.CREATING:
                child.state = TupleState.ABORTING # Abort if not yet processed
            elif not child.state.is_dirty():
                child.state = TupleState.DYING    # Schedule for retraction
                self.scheduler.schedule(child)

    # --- AbstractNode Contract Fulfillment ---
    def insert(self, tuple_):
        """Directional inserts (insert_left/right) must be used via adapters."""
        raise NotImplementedError("BaseJoinNode requires directional insert.")

    def retract(self, tuple_):
        """Directional retractions (retract_left/right) must be used via adapters."""
        raise NotImplementedError("BaseJoinNode requires directional retract.")
