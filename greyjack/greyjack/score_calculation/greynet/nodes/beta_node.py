from __future__ import annotations
from abc import ABC, abstractmethod

from ..nodes.abstract_node import AbstractNode
from ..common.index.uni_index import UniIndex
from ..common.index.advanced_index import AdvancedIndex
from ..core.tuple import TupleState, AbstractTuple
from ..common.joiner_type import JoinerType

# --- Start of Bug Fix ---
# Defines the logical inverse for each joiner type, which is essential for
# creating symmetrical join logic within the BetaNode.
JOINER_INVERSES = {
    JoinerType.EQUAL: JoinerType.EQUAL,
    JoinerType.NOT_EQUAL: JoinerType.NOT_EQUAL,
    JoinerType.LESS_THAN: JoinerType.GREATER_THAN,
    JoinerType.LESS_THAN_OR_EQUAL: JoinerType.GREATER_THAN_OR_EQUAL,
    JoinerType.GREATER_THAN: JoinerType.LESS_THAN,
    JoinerType.GREATER_THAN_OR_EQUAL: JoinerType.LESS_THAN_OR_EQUAL,
    JoinerType.RANGE_OVERLAPS: JoinerType.RANGE_OVERLAPS,
    JoinerType.RANGE_CONTAINS: JoinerType.RANGE_WITHIN,
    JoinerType.RANGE_WITHIN: JoinerType.RANGE_CONTAINS,
}
# --- End of Bug Fix ---


class BetaNode(AbstractNode, ABC):
    """
    An abstract base class for all join nodes (Bi, Tri, Quad, etc.).
    It contains the common logic for indexing, matching, and propagating tuples.
    """
    def __init__(self, node_id, joiner_type, left_index_properties, right_index_properties, scheduler, tuple_pool):
        super().__init__(node_id)
        self.scheduler = scheduler
        self.tuple_pool = tuple_pool
        self.joiner_type = joiner_type
        
        # --- Start of Bug Fix ---
        # The join is defined from left to right (e.g., left.key < right.key).
        # When a new right_tuple arrives, we probe the left_index to find left_tuples
        # that satisfy the original joiner (e.g., left.key < new_right.key).
        self.left_index = self._create_index(left_index_properties, joiner_type)

        # When a new left_tuple arrives, we must probe the right_index using the
        # inverse joiner to find right_tuples that satisfy the condition.
        # e.g., to find 'right' where 'new_left.key < right.key', we must query for
        # 'right.key > new_left.key'.
        inverse_joiner = JOINER_INVERSES.get(joiner_type)
        if inverse_joiner is None:
            raise ValueError(f"Joiner type {joiner_type} has no defined inverse.")
        self.right_index = self._create_index(right_index_properties, inverse_joiner)
        # --- End of Bug Fix ---
        
        self.beta_memory = {}

    def __repr__(self) -> str:
        """Overrides base representation to include the joiner type."""
        return f"<{self.__class__.__name__} id={self._node_id} joiner={self.joiner_type.name}>"


    def _create_index(self, props, joiner):
        """Factory method to create the appropriate index based on joiner type."""
        if joiner == JoinerType.EQUAL:
            return UniIndex(props)
        return AdvancedIndex(props, joiner)

    @abstractmethod
    def _create_child_tuple(self, left_tuple: AbstractTuple, right_tuple: AbstractTuple) -> AbstractTuple:
        """Abstract method to be implemented by subclasses to create the correct child tuple type."""
        pass

    def insert_left(self, left_tuple: AbstractTuple):
        self.left_index.put(left_tuple)
        key = self.left_index._index_properties.get_property(left_tuple)
        right_matches = self.right_index.get_matches(key) if hasattr(self.right_index, 'get_matches') else self.right_index.get(key)
        for right_tuple in right_matches:
            self.create_and_schedule_child(left_tuple, right_tuple)

    def insert_right(self, right_tuple: AbstractTuple):
        self.right_index.put(right_tuple)
        key = self.right_index._index_properties.get_property(right_tuple)
        left_matches = self.left_index.get_matches(key) if hasattr(self.left_index, 'get_matches') else self.left_index.get(key)
        for left_tuple in left_matches:
            self.create_and_schedule_child(left_tuple, right_tuple)

    def retract_left(self, left_tuple: AbstractTuple):
        self.left_index.remove(left_tuple)
        pairs_to_remove = [p for p in self.beta_memory if p[0] == left_tuple]
        for pair in pairs_to_remove:
            self.retract_and_schedule_child(pair[0], pair[1])

    def retract_right(self, right_tuple: AbstractTuple):
        self.right_index.remove(right_tuple)
        pairs_to_remove = [p for p in self.beta_memory if p[1] == right_tuple]
        for pair in pairs_to_remove:
            self.retract_and_schedule_child(pair[0], pair[1])

    def create_and_schedule_child(self, left_tuple: AbstractTuple, right_tuple: AbstractTuple):
        child = self._create_child_tuple(left_tuple, right_tuple)
        child.node, child.state = self, TupleState.CREATING
        self.beta_memory[(left_tuple, right_tuple)] = child
        self.scheduler.schedule(child)

    def retract_and_schedule_child(self, left: AbstractTuple, right: AbstractTuple):
        child = self.beta_memory.pop((left, right), None)
        if child:
            if child.state == TupleState.CREATING:
                child.state = TupleState.ABORTING
            elif not child.state.is_dirty():
                child.state = TupleState.DYING
                self.scheduler.schedule(child)

    def insert(self, tuple_):
        raise NotImplementedError("BetaNode requires directional insert via an adapter.")

    def retract(self, tuple_):
        raise NotImplementedError("BetaNode requires directional retract via an adapter.")
