from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Type, Callable, TYPE_CHECKING, Any
from datetime import datetime, timedelta

from ..common.index_properties import IndexProperties
from ..tuple_tools import get_arity, ARITY_TO_TUPLE, get_facts
from ..nodes.filter_node import FilterNode
from ..nodes.join_node import JoinNode
from ..nodes.group_node import GroupNode
from ..nodes.from_uni_node import FromUniNode
from ..nodes.flatmap_node import FlatMapNode
from ..nodes.conditional_node import ConditionalNode
from .join_adapters import JoinLeftAdapter, JoinRightAdapter
from ..function import Function

if TYPE_CHECKING:
    from .stream import Stream
    from ..constraint_factory import ConstraintFactory
    from ..core.tuple_pool import TuplePool
    from ..core.tuple import AbstractTuple
    from ..nodes.abstract_node import AbstractNode

class StreamDefinition(ABC):
    """An abstract base class for defining the behavior of a stream node."""
    def __init__(self, factory: 'ConstraintFactory', source_stream: Stream = None):
        self.factory = factory
        self.source_stream = source_stream
        self.retrieval_id = None # Must be set by subclasses

    @abstractmethod
    def build_node(self, node_counter, node_map, scheduler, tuple_pool: TuplePool) -> 'AbstractNode':
        """Builds and returns the corresponding Rete node(s) for this definition."""
        pass
    
    @abstractmethod
    def get_target_arity(self) -> int:
        """Returns the arity of the tuple this stream will produce."""
        pass

class FromDefinition(StreamDefinition):
    """Definition for a stream originating from facts."""
    def __init__(self, factory: 'ConstraintFactory', fact_class: Type):
        super().__init__(factory)
        self.fact_class = fact_class
        self.retrieval_id = ('from', fact_class)

    def get_target_arity(self) -> int: return 1

    def build_node(self, node_counter, node_map, scheduler, tuple_pool: 'TuplePool') -> 'AbstractNode':
        node = node_map.get(self.retrieval_id)
        if node is None:
            node_id = node_counter.value; node_counter.value += 1
            node = FromUniNode(node_id, self.fact_class, scheduler, tuple_pool)
            node_map[self.retrieval_id] = node
        return node

class FilterDefinition(StreamDefinition):
    """Definition for a filter operation."""
    def __init__(self, factory: 'ConstraintFactory', source_stream: 'Stream', predicate: Callable):
        super().__init__(factory, source_stream)
        self.predicate = predicate
        self.retrieval_id = ('filter', source_stream.definition.retrieval_id, predicate)

    def get_target_arity(self) -> int:
        return self.source_stream.arity

    def build_node(self, node_counter, node_map, scheduler, tuple_pool: 'TuplePool') -> 'AbstractNode':
        node = self.factory.node_sharer.get_or_create_node(
            self.retrieval_id, self.factory.node_sharer.alpha_nodes,
            lambda: self._create_node(node_counter, scheduler)
        )
        if self.retrieval_id not in node_map:
            parent_node = self.source_stream.definition.build_node(node_counter, node_map, scheduler, tuple_pool)
            parent_node.add_child_node(node)
            node_map[self.retrieval_id] = node
        return node

    def _create_node(self, node_counter, scheduler) -> 'AbstractNode':
        node_id = node_counter.value; node_counter.value += 1
        wrapped_predicate = lambda t: self.predicate(*get_facts(t))
        return FilterNode(node_id, wrapped_predicate, scheduler)

class JoinDefinition(StreamDefinition):
    """Definition for a join operation."""
    def __init__(self, factory: 'ConstraintFactory', left_stream: 'Stream', right_stream: 'Stream',
                 joiner_type, left_key_func: Callable, right_key_func: Callable):
        super().__init__(factory, left_stream)
        self.right_stream = right_stream
        self.joiner_type = joiner_type
        self.left_key_func = left_key_func
        self.right_key_func = right_key_func
        self.retrieval_id = (
            'join', left_stream.definition.retrieval_id, right_stream.definition.retrieval_id,
            joiner_type, left_key_func, right_key_func
        )

    def get_target_arity(self) -> int:
        return self.source_stream.arity + self.right_stream.arity

    def build_node(self, node_counter, node_map, scheduler, tuple_pool: 'TuplePool') -> 'AbstractNode':
        node = self.factory.node_sharer.get_or_create_node(
            self.retrieval_id, self.factory.node_sharer.beta_nodes,
            lambda: self._create_node(node_counter, scheduler, tuple_pool)
        )
        if self.retrieval_id not in node_map:
            left_node = self.source_stream.definition.build_node(node_counter, node_map, scheduler, tuple_pool)
            right_node = self.right_stream.definition.build_node(node_counter, node_map, scheduler, tuple_pool)
            left_node.add_child_node(JoinLeftAdapter(node))
            right_node.add_child_node(JoinRightAdapter(node))
            node_map[self.retrieval_id] = node
        return node

    def _create_node(self, node_counter, scheduler, tuple_pool) -> 'AbstractNode':
        target_arity = self.get_target_arity()
        if target_arity > 5:
            raise ValueError("Joining would result in an arity greater than 5, which is not supported.")
        child_tuple_class = ARITY_TO_TUPLE[target_arity]
        
        node_id = node_counter.value; node_counter.value += 1
        left_props = IndexProperties(lambda t: self.left_key_func(*get_facts(t)))
        right_props = IndexProperties(lambda t: self.right_key_func(*get_facts(t)))
        
        return JoinNode(
            node_id, self.joiner_type, left_props, right_props,
            scheduler, tuple_pool, child_tuple_class
        )

class GroupByDefinition(StreamDefinition):
    """Definition for a group_by operation."""
    def __init__(self, factory: 'ConstraintFactory', source_stream: 'Stream',
                 group_key_function: Callable, collector_supplier: Callable):
        super().__init__(factory, source_stream)
        self.group_key_function = group_key_function
        self.collector_supplier = collector_supplier
        self.retrieval_id = ('group_by', source_stream.definition.retrieval_id, group_key_function, collector_supplier)

    def get_target_arity(self) -> int: return 2

    def build_node(self, node_counter, node_map, scheduler, tuple_pool: 'TuplePool') -> 'AbstractNode':
        node = self.factory.node_sharer.get_or_create_node(
            self.retrieval_id, self.factory.node_sharer.group_nodes,
            lambda: self._create_node(node_counter, scheduler, tuple_pool)
        )
        if self.retrieval_id not in node_map:
            parent_node = self.source_stream.definition.build_node(node_counter, node_map, scheduler, tuple_pool)
            parent_node.add_child_node(node)
            node_map[self.retrieval_id] = node
        return node
        
    def _create_node(self, node_counter, scheduler, tuple_pool) -> 'AbstractNode':
        node_id = node_counter.value; node_counter.value += 1
        wrapped_fact_group_key = lambda fact: self.group_key_function(fact)
        return GroupNode(node_id, wrapped_fact_group_key, self.collector_supplier, scheduler, tuple_pool)

class ConditionalJoinDefinition(StreamDefinition):
    """Definition for an if_exists or if_not_exists operation."""
    def __init__(self, factory: 'ConstraintFactory', source_stream: 'Stream', left_stream: 'Stream', right_stream: 'Stream',
                 should_exist: bool, left_key_func: Callable, right_key_func: Callable):
        super().__init__(factory, source_stream)
        self.left_stream = left_stream
        self.right_stream = right_stream
        self.should_exist = should_exist
        self.left_key_func = left_key_func
        self.right_key_func = right_key_func
        self.retrieval_id = (
            'cond_join', left_stream.definition.retrieval_id, right_stream.definition.retrieval_id,
            should_exist, left_key_func, right_key_func
        )

    def get_target_arity(self) -> int: return self.left_stream.arity

    def build_node(self, node_counter, node_map, scheduler, tuple_pool: 'TuplePool') -> 'AbstractNode':
        node = self.factory.node_sharer.get_or_create_node(
            self.retrieval_id, self.factory.node_sharer.beta_nodes,
            lambda: self._create_node(node_counter, scheduler, tuple_pool)
        )
        if self.retrieval_id not in node_map:
            left_node = self.left_stream.definition.build_node(node_counter, node_map, scheduler, tuple_pool)
            right_node = self.right_stream.definition.build_node(node_counter, node_map, scheduler, tuple_pool)
            left_node.add_child_node(JoinLeftAdapter(node))
            right_node.add_child_node(JoinRightAdapter(node))
            node_map[self.retrieval_id] = node
        return node

    def _create_node(self, node_counter, scheduler, tuple_pool) -> 'AbstractNode':
        node_id = node_counter.value; node_counter.value += 1
        left_props = IndexProperties(lambda t: self.left_key_func(*get_facts(t)))
        right_props = IndexProperties(lambda t: self.right_key_func(*get_facts(t)))
        return ConditionalNode(
            node_id, left_props, right_props, self.should_exist, scheduler
        )

class FlatMapDefinition(StreamDefinition):
    """Definition for a flat_map operation."""
    def __init__(self, factory: 'ConstraintFactory', source_stream: 'Stream', mapper: Callable):
        super().__init__(factory, source_stream)
        self.mapper = mapper
        self.retrieval_id = ('flat_map', source_stream.definition.retrieval_id, mapper)

    def get_target_arity(self) -> int: return 1

    def build_node(self, node_counter, node_map, scheduler, tuple_pool: 'TuplePool') -> 'AbstractNode':
        node = node_map.get(self.retrieval_id)
        if node is None:
            node = self._create_node(node_counter, scheduler, tuple_pool)
            parent_node = self.source_stream.definition.build_node(node_counter, node_map, scheduler, tuple_pool)
            parent_node.add_child_node(node)
            node_map[self.retrieval_id] = node
        return node
        
    def _create_node(self, node_counter, scheduler, tuple_pool) -> 'AbstractNode':
        node_id = node_counter.value; node_counter.value += 1
        
        class FlatMapWrapper(Function):
            def __init__(self, mapper_callable):
                self.mapper = mapper_callable
            
            def apply(self, parent_tuple: 'AbstractTuple'):
                return self.mapper(*get_facts(parent_tuple))

        final_mapper_obj = FlatMapWrapper(self.mapper)
        
        return FlatMapNode(node_id, final_mapper_obj, scheduler, tuple_pool)