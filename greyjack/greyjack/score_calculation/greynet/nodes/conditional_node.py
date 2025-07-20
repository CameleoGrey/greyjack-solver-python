from ..nodes.abstract_node import AbstractNode
from ..common.index.uni_index import UniIndex

class ConditionalNode(AbstractNode):
    def __init__(self, node_id, left_props, right_props, should_exist, scheduler):
        super().__init__(node_id)
        self.left_properties = left_props
        self.right_properties = right_props
        self.should_exist = should_exist
        self.scheduler = scheduler
        self.left_index = UniIndex(left_props)
        self.right_index = UniIndex(right_props)
        self.tuple_map = {} # Tracks propagated tuples
    
    def __repr__(self) -> str:
        """Overrides base representation to show the condition type."""
        condition = "EXISTS" if self.should_exist else "NOT EXISTS"
        return f"<{self.__class__.__name__} id={self._node_id} condition='{condition}'>"

    def insert_left(self, tuple_):
        key = self.left_properties.get_property(tuple_)
        self.left_index.put(tuple_)
        has_matches = bool(self.right_index.get(key))
        if has_matches == self.should_exist:
            self.propagate(tuple_)
        else:
            pass

    def insert_right(self, tuple_):
        key = self.right_properties.get_property(tuple_)
        was_empty = not self.right_index.get(key)
        self.right_index.put(tuple_)
        
        if was_empty:
            if self.should_exist:
                for left_tuple in self.left_index.get(key):
                    self.propagate(left_tuple)
            else:
                for left_tuple in self.left_index.get(key):
                    self.retract_propagation(left_tuple)

    def retract_left(self, tuple_):
        self.left_index.remove(tuple_)
        self.retract_propagation(tuple_)

    def retract_right(self, tuple_):
        key = self.right_properties.get_property(tuple_)
        self.right_index.remove(tuple_)
        is_now_empty = not self.right_index.get(key)

        if is_now_empty:
            if self.should_exist:
                for left_tuple in self.left_index.get(key):
                    self.retract_propagation(left_tuple)
            else:
                for left_tuple in self.left_index.get(key):
                    self.propagate(left_tuple)

    def propagate(self, tuple_):
        if tuple_ not in self.tuple_map:
            self.tuple_map[tuple_] = tuple_
            self.calculate_downstream([tuple_])

    def retract_propagation(self, tuple_):
        if tuple_ in self.tuple_map:
            del self.tuple_map[tuple_]
            self.retract_downstream([tuple_])
    
    def insert(self, tuple_): raise NotImplementedError("ConditionalNode requires directional insert.")
    def retract(self, tuple_): raise NotImplementedError("ConditionalNode requires directional retract.")
