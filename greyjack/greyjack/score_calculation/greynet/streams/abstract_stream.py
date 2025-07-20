from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Union, TYPE_CHECKING

from ..constraint import Constraint
from ..common.index_properties import IndexProperties
from ..function import Function

if TYPE_CHECKING:
    from ..constraint_factory import ConstraintFactory
    from ..core.tuple_pool import TuplePool


class AbstractStream(ABC):
    def __init__(self, constraint_factory: 'ConstraintFactory', retrieval_id):
        self.constraint_factory = constraint_factory
        self.retrieval_id = retrieval_id
        self.next_streams = []
        self.source_stream = None

    def add_next_stream(self, stream: AbstractStream):
        self.next_streams.append(stream)

    def and_source(self, stream: AbstractStream):
        self.source_stream = stream

    def _create_penalty(self, score_type: str, penalty: Union[int, float, Callable]) -> Constraint:
        """Helper to package stream and penalty info into a Constraint object."""
        penalty_function = penalty
        if not callable(penalty_function):
            penalty_function = lambda *facts: penalty
        
        return Constraint(stream=self, score_type=score_type, penalty_function=penalty_function)

    def penalize_hard(self, penalty: Union[int, float, Callable]) -> Constraint:
        return self._create_penalty("hard", penalty)

    def penalize_medium(self, penalty: Union[int, float, Callable]) -> Constraint:
        return self._create_penalty("medium", penalty)

    def penalize_soft(self, penalty: Union[int, float, Callable]) -> Constraint:
        return self._create_penalty("soft", penalty)

    def penalize_simple(self, penalty: Union[int, float, Callable]) -> Constraint:
        return self._create_penalty("simple", penalty)

    @abstractmethod
    def build_node(self, node_counter, node_map, scheduler, tuple_pool: TuplePool):
       pass
