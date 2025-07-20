from collections import deque
from ..core.scheduler import Scheduler
from ..core.tuple import TupleState
from ..core.tuple_pool import TuplePool


class BatchScheduler(Scheduler):
    def __init__(self, node_map, tuple_pool: TuplePool, batch_size=100):
        super().__init__(node_map)
        self.batch_size = batch_size
        self.pending_queue = deque()
        self.tuple_pool = tuple_pool

    def schedule(self, tuple_):
        self.pending_queue.append(tuple_)

    def fire_all(self):
        """Processes all pending tuple changes in the queue."""
        while self.pending_queue:
            tuple_ = self.pending_queue.popleft()
            node = tuple_.node
            state = tuple_.state

            if state == TupleState.CREATING:
                node.calculate_downstream([tuple_])
                tuple_.state = TupleState.OK
            elif state == TupleState.UPDATING:
                node.retract_downstream([tuple_])
                node.calculate_downstream([tuple_])
                tuple_.state = TupleState.OK
            elif state == TupleState.DYING:
                node.retract_downstream([tuple_])
                tuple_.state = TupleState.DEAD
            elif state == TupleState.ABORTING:
                tuple_.state = TupleState.DEAD
            
            # If the tuple is now dead, release it back to the pool.
            if tuple_.state == TupleState.DEAD:
                self.tuple_pool.release(tuple_)
