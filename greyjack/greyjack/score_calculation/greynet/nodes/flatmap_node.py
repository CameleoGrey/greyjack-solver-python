from __future__ import annotations
from typing import TYPE_CHECKING
from .abstract_node import AbstractNode
from ..core.tuple import UniTuple, TupleState
from ..function import Function

if TYPE_CHECKING:
    from ..core.tuple_pool import TuplePool
    from ..core.tuple import AbstractTuple

class FlatMapNode(AbstractNode):
    def __init__(self, node_id: int, mapper: Function, scheduler, tuple_pool: 'TuplePool'):
        super().__init__(node_id)
        self.mapper = mapper
        self.scheduler = scheduler
        self.tuple_pool = tuple_pool
        self.parent_to_children_map = {}

    def insert(self, tuple_: 'AbstractTuple'):
        
        generated_items = self.mapper.apply(tuple_)
        if not generated_items:
            return

        child_tuples = []
        for item in generated_items:
            child_tuple = self.tuple_pool.acquire(UniTuple, fact_a=item)
            child_tuple.node = self
            child_tuple.state = TupleState.CREATING
            self.scheduler.schedule(child_tuple)
            child_tuples.append(child_tuple)

        if child_tuples:
            self.parent_to_children_map[tuple_] = child_tuples

    def retract(self, tuple_: 'AbstractTuple'):
        
        child_tuples = self.parent_to_children_map.pop(tuple_, [])
        if not child_tuples:
            return

        for child in child_tuples:
            if child.state == TupleState.CREATING:
                child.state = TupleState.ABORTING
            elif not child.state.is_dirty():
                child.state = TupleState.DYING
                self.scheduler.schedule(child)
