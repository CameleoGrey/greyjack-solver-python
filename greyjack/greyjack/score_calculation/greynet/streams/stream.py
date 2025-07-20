from __future__ import annotations
from typing import Generic, TypeVar, Callable, Type, Union, TYPE_CHECKING, Any, Iterable, List
from datetime import timedelta, datetime

from ..constraint import Constraint
from ..tuple_tools import get_facts
from .stream_definition import (
    FilterDefinition, JoinDefinition,
    GroupByDefinition, ConditionalJoinDefinition, FlatMapDefinition,
)
from ..core.tuple import UniTuple, BiTuple, AbstractTuple

if TYPE_CHECKING:
    from ..constraint_factory import ConstraintFactory
    from ..core.tuple import AbstractTuple
    from ..common.joiner_type import JoinerType
    from .stream_definition import StreamDefinition


T_Tuple = TypeVar('T_Tuple', bound='AbstractTuple')

class Stream(Generic[T_Tuple]):
    """A generic, unified stream for processing tuples of any arity."""
    
    def __init__(self, factory: 'ConstraintFactory', definition: 'StreamDefinition'):
        self.constraint_factory = factory
        self.definition = definition
        self.arity = definition.get_target_arity()
        self.next_streams: list[Stream] = []

    def _add_next_stream(self, stream: 'Stream'):
        self.next_streams.append(stream)

    def filter(self, predicate: Callable[..., bool]) -> Stream[T_Tuple]:
        """Filters the stream based on a predicate."""
        filter_def = FilterDefinition(self.constraint_factory, self, predicate)
        new_stream = Stream[T_Tuple](self.constraint_factory, filter_def)
        self._add_next_stream(new_stream)
        return new_stream

    def join(self, other_stream: Stream[Any], joiner_type: 'JoinerType',
             left_key_func: Callable[..., Any], right_key_func: Callable[..., Any]) -> Stream[AbstractTuple]:
        """Joins this stream with another stream."""
        join_def = JoinDefinition(
            self.constraint_factory, self, other_stream,
            joiner_type, left_key_func, right_key_func
        )
        new_stream = Stream[AbstractTuple](self.constraint_factory, join_def)
        self._add_next_stream(new_stream)
        other_stream._add_next_stream(new_stream)
        return new_stream

    def group_by(self, group_key_function: Callable[..., Any], collector_supplier: Callable) -> Stream['BiTuple']:
        """Groups tuples by a key and applies a collector, returning a stream of (key, result) BiTuples."""
        group_by_def = GroupByDefinition(self.constraint_factory, self, group_key_function, collector_supplier)
        new_stream = Stream[BiTuple](self.constraint_factory, group_by_def)
        self._add_next_stream(new_stream)
        return new_stream

    def if_exists(self, other_stream: Stream[Any], left_key: Callable[..., Any], 
                  right_key: Callable[..., Any]) -> Stream[T_Tuple]:
        """Propagates tuples only if a match exists in the other stream."""
        # Allow passing a fact class directly for convenience
        if not isinstance(other_stream, Stream):
             other_stream = self.constraint_factory.from_(other_stream)

        cond_def = ConditionalJoinDefinition(
            self.constraint_factory, self, self, other_stream, True,
            left_key, right_key
        )
        new_stream = Stream[T_Tuple](self.constraint_factory, cond_def)
        self._add_next_stream(new_stream)
        other_stream._add_next_stream(new_stream)
        return new_stream
        
    def if_not_exists(self, other_stream: Stream[Any], left_key: Callable[..., Any], 
                      right_key: Callable[..., Any]) -> Stream[T_Tuple]:
        """Propagates tuples only if no match exists in the other stream."""
        # Allow passing a fact class directly for convenience
        if not isinstance(other_stream, Stream):
             other_stream = self.constraint_factory.from_(other_stream)

        cond_def = ConditionalJoinDefinition(
            self.constraint_factory, self, self, other_stream, False,
            left_key, right_key
        )
        new_stream = Stream[T_Tuple](self.constraint_factory, cond_def)
        self._add_next_stream(new_stream)
        other_stream._add_next_stream(new_stream)
        return new_stream

    def flat_map(self, mapper: Callable[..., Iterable[Any]]) -> Stream['UniTuple']:
        """Transforms each element into an iterable of new elements, flattening the result."""
        flat_map_def = FlatMapDefinition(self.constraint_factory, self, mapper)
        new_stream = Stream[UniTuple](self.constraint_factory, flat_map_def)
        self._add_next_stream(new_stream)
        return new_stream

    def map(self, mapper: Callable[..., Any]) -> Stream['UniTuple']:
        """Transforms each element into a single new element."""
        wrapped_mapper = lambda *facts: [mapper(*facts)]
        return self.flat_map(wrapped_mapper)

    def build_node(self, node_counter, node_map, scheduler, tuple_pool):
        """Builds the Rete node for this stream and wires its children."""
        node = self.definition.build_node(node_counter, node_map, scheduler, tuple_pool)
        return node

    # --- Penalty Methods ---
    def _create_penalty(self, score_type: str, penalty: Union[int, float, Callable]) -> Constraint:
        penalty_function = penalty
        if not callable(penalty_function):
            penalty_function = lambda *facts: penalty
        
        def impact_wrapper(*facts):
             return penalty_function(*facts)

        return Constraint(stream=self, score_type=score_type, penalty_function=impact_wrapper)

    def penalize_hard(self, penalty: Union[int, float, Callable]) -> Constraint:
        return self._create_penalty("hard", penalty)

    def penalize_soft(self, penalty: Union[int, float, Callable]) -> Constraint:
        return self._create_penalty("soft", penalty)

    def penalize_medium(self, penalty: Union[int, float, Callable]) -> Constraint:
        return self._create_penalty("medium", penalty)

    def penalize_simple(self, penalty: Union[int, float, Callable]) -> Constraint:
        return self._create_penalty("simple", penalty)