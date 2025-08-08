from __future__ import annotations
from abc import ABC, abstractmethod
from collections import defaultdict

from ..nodes.abstract_node import AbstractNode
from ..common.index.uni_index import UniIndex
from ..common.index.advanced_index import AdvancedIndex
from ..core.tuple import TupleState, AbstractTuple
from ..common.joiner_type import JoinerType

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


class BetaNode(AbstractNode, ABC):
    """
    An abstract base class for all join nodes (Bi, Tri, Quad, etc.).
    It contains the common logic for indexing, matching, and propagating tuples.
    This version includes reverse indices for O(1) retraction performance.
    """
    def __init__(self, node_id, joiner_type, left_index_properties, right_index_properties, scheduler, tuple_pool):
        super().__init__(node_id)
        self.scheduler = scheduler
        self.tuple_pool = tuple_pool
        self.joiner_type = joiner_type

        self.left_index = self._create_index(left_index_properties, joiner_type)
        inverse_joiner = JOINER_INVERSES.get(joiner_type)
        if inverse_joiner is None:
            raise ValueError(f"Joiner type {joiner_type} has no defined inverse.")
        self.right_index = self._create_index(right_index_properties, inverse_joiner)

        self.beta_memory = {}
        self.left_to_pairs = defaultdict(list)
        self.right_to_pairs = defaultdict(list)

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
        """Handles insertion of a tuple from the left parent."""
        self.left_index.put(left_tuple)
        key = self.left_index._index_properties.get_property(left_tuple)
        # Probe the opposing index for matches
        right_matches = self.right_index.get_matches(key) if hasattr(self.right_index, 'get_matches') else self.right_index.get(key)
        for right_tuple in right_matches:
            self.create_and_propagate_child(left_tuple, right_tuple)

    def insert_right(self, right_tuple: AbstractTuple):
        """Handles insertion of a tuple from the right parent."""
        self.right_index.put(right_tuple)
        key = self.right_index._index_properties.get_property(right_tuple)
        # Probe the opposing index for matches
        left_matches = self.left_index.get_matches(key) if hasattr(self.left_index, 'get_matches') else self.left_index.get(key)
        for left_tuple in left_matches:
            self.create_and_propagate_child(left_tuple, right_tuple)

    def retract_left(self, left_tuple: AbstractTuple):
        """Handles retraction of a tuple from the left parent using the reverse index."""
        self.left_index.remove(left_tuple)
        
        if left_tuple in self.left_to_pairs:
            pairs_to_remove = list(self.left_to_pairs[left_tuple])
            
            for pair in pairs_to_remove:
                self.retract_and_propagate_child(pair)

    def retract_right(self, right_tuple: AbstractTuple):
        """Handles retraction of a tuple from the right parent using the reverse index."""
        self.right_index.remove(right_tuple)
        
        if right_tuple in self.right_to_pairs:
            pairs_to_remove = list(self.right_to_pairs[right_tuple])
            
            for pair in pairs_to_remove:
                self.retract_and_propagate_child(pair)

    def create_and_propagate_child(self, left_tuple: AbstractTuple, right_tuple: AbstractTuple):
        """Creates a new child tuple, stores it, updates indices, and schedules propagation."""
        pair = (left_tuple, right_tuple)
        if pair in self.beta_memory:
            return  # Avoid creating duplicate children

        child = self._create_child_tuple(left_tuple, right_tuple)
        child.node, child.state = self, TupleState.CREATING
        self.beta_memory[pair] = child

        self.left_to_pairs[left_tuple].append(pair)
        self.right_to_pairs[right_tuple].append(pair)

        self.scheduler.schedule(child)

    def retract_and_propagate_child(self, pair: tuple[AbstractTuple, AbstractTuple]):
        """Removes a child tuple, cleans up all indices, and schedules retraction."""
        child = self.beta_memory.pop(pair, None)
        if child:
            left, right = pair
            if left in self.left_to_pairs:
                self.left_to_pairs[left].remove(pair)
                if not self.left_to_pairs[left]:
                    del self.left_to_pairs[left]
            
            if right in self.right_to_pairs:
                self.right_to_pairs[right].remove(pair)
                if not self.right_to_pairs[right]:
                    del self.right_to_pairs[right]

            if child.state == TupleState.CREATING:
                child.state = TupleState.ABORTING
            elif not child.state.is_dirty():
                child.state = TupleState.DYING
                self.scheduler.schedule(child)

    def insert(self, tuple_):
        raise NotImplementedError("BetaNode requires directional insert via an adapter.")

    def retract(self, tuple_):
        raise NotImplementedError("BetaNode requires directional retract via an adapter.")
