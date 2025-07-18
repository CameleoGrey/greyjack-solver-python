from __future__ import annotations
from typing import Type

from .nodes.from_uni_node import FromUniNode
from .nodes.scoring_node import ScoringNode
from .session import Session
from .optimization.batch_processor import BatchScheduler
from .core.tuple_pool import TuplePool
from .optimization.node_sharing import NodeSharingManager
from .streams.stream import Stream
from .streams.stream_definition import FromDefinition
from .core.tuple import UniTuple

class ConstraintFactory:
    def __init__(self, package_name: str, score_class: Type):
        self.package_name = package_name
        self.score_class = score_class
        self._constraint_defs = []
        self.tuple_pool = TuplePool()
        self.node_sharer = NodeSharingManager()

    def from_(self, from_class) -> Stream[UniTuple]:
        """Creates a new Stream originating from a fact class."""
        from_def = FromDefinition(self, from_class)
        return Stream[UniTuple](self, from_def)


    def add_constraint(self, constraint_def):
        self._constraint_defs.append(constraint_def)

    def build_session(self, **kwargs) -> Session:
        class Counter:
            def __init__(self): self.value = 0
        node_counter = Counter()

        weights = kwargs.pop('weights', None)

        session_node_map = {}
        scheduler = BatchScheduler(
            session_node_map,
            self.tuple_pool,
            kwargs.get("batch_size", 100)
        )

        for constraint_def in self._constraint_defs:
            final_stream = constraint_def()
            final_stream.build_node(node_counter, session_node_map, scheduler, self.tuple_pool)

        from_nodes, scoring_nodes = {}, []
        for node in session_node_map.values():
            if isinstance(node, FromUniNode):
                from_nodes[node.retrieval_id] = node
            elif isinstance(node, ScoringNode):
                scoring_nodes.append(node)

        return Session(from_nodes, scoring_nodes, scheduler, self.score_class, self.tuple_pool, weights)
