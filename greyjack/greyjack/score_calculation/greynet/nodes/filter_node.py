from __future__ import annotations
from typing import Callable
from .abstract_node import AbstractNode
from ..core.tuple import AbstractTuple

class FilterNode(AbstractNode):
    """A generic node that filters tuples of any arity based on a predicate."""
    def __init__(self, node_id: int, predicate: Callable[[AbstractTuple], bool], scheduler):
        super().__init__(node_id)
        self.predicate = predicate
        self.scheduler = scheduler

    def insert(self, tuple_: AbstractTuple):
        """If the tuple satisfies the predicate, it is propagated."""
        if self.predicate(tuple_):
            self.calculate_downstream([tuple_])
        else:
            pass

    def retract(self, tuple_: AbstractTuple):
        """If the tuple satisfied the predicate, its retraction is propagated."""
        if self.predicate(tuple_):
            self.retract_downstream([tuple_])
