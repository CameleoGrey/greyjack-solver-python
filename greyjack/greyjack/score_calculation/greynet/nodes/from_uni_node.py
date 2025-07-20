from ..nodes.abstract_node import AbstractNode
from ..core.tuple import UniTuple, TupleState

class FromUniNode(AbstractNode):
    def __init__(self, node_id, retrieval_id, scheduler, tuple_pool):
        super().__init__(node_id)
        self.retrieval_id = retrieval_id
        self.scheduler = scheduler
        self.tuple_pool = tuple_pool
    
    def __repr__(self) -> str:
        """Overrides base representation to show the source fact class."""
        return f"<{self.__class__.__name__} id={self._node_id} fact_class={self.retrieval_id.__name__}>"


    def insert(self, fact):
        # Use the pool to acquire a tuple instead of direct instantiation.
        tuple_ = self.tuple_pool.acquire(UniTuple, fact_a=fact)
        tuple_.node = self
        tuple_.state = TupleState.CREATING
        self.scheduler.schedule(tuple_)
        return tuple_

    def retract(self, tuple_):
        if tuple_.state == TupleState.CREATING:
            tuple_.state = TupleState.ABORTING
        elif not tuple_.state.is_dirty():
            tuple_.state = TupleState.DYING
            self.scheduler.schedule(tuple_)
