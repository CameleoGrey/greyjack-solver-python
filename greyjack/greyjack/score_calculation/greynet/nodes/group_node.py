from ..nodes.abstract_node import AbstractNode
from ..core.tuple import BiTuple, TupleState

class GroupNode(AbstractNode):
    def __init__(self, node_id, group_key_function, collector_supplier, scheduler, tuple_pool):
        super().__init__(node_id)
        self.group_key_function = group_key_function 
        self.collector_supplier = collector_supplier
        self.scheduler = scheduler
        self.group_map = {}
        self.tuple_to_undo = {}
        self.group_key_to_tuple = {}
        self.tuple_pool = tuple_pool 

    def insert(self, tuple_):
        fact = tuple_.fact_a
        group_key = self.group_key_function(fact)
        
        if group_key not in self.group_map:
            self.group_map[group_key] = self.collector_supplier()

        collector = self.group_map[group_key]
        undo_function = collector.insert(fact)
        self.tuple_to_undo[tuple_] = (group_key, undo_function)

        self._update_or_create_child(group_key, collector)

    def retract(self, tuple_):
        if tuple_ not in self.tuple_to_undo: return
        group_key, undo_function = self.tuple_to_undo.pop(tuple_)
        undo_function()

        collector = self.group_map.get(group_key)
        if collector:
            if collector.is_empty():
                self._retract_child_by_key(group_key)
                del self.group_map[group_key]
            else:
                self._update_or_create_child(group_key, collector)

    def _update_or_create_child(self, group_key, collector):
        child_tuple = self.group_key_to_tuple.get(group_key)
        new_result = collector.result()

        if child_tuple:
            if child_tuple.fact_b == new_result:
                return
            self._retract_child_by_key(group_key)
        
        self._create_child(group_key, new_result)

    def _create_child(self, key, result):
        tuple_ = self.tuple_pool.acquire(BiTuple, fact_a=key, fact_b=result)
        tuple_.node, tuple_.state = self, TupleState.CREATING
        self.group_key_to_tuple[key] = tuple_
        self.scheduler.schedule(tuple_)

    def _retract_child_by_key(self, key):
        if key in self.group_key_to_tuple:
            tuple_ = self.group_key_to_tuple.pop(key)
            if tuple_.state == TupleState.CREATING:
                tuple_.state = TupleState.ABORTING
            elif not tuple_.state.is_dirty():
                tuple_.state = TupleState.DYING
                self.scheduler.schedule(tuple_)
