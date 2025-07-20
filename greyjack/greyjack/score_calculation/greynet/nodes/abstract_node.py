# greynet/nodes/abstract_node.py
from abc import ABC, abstractmethod

class AbstractNode(ABC):
    def __init__(self, node_id):
        self._node_id = node_id
        self.child_nodes = []

    def __repr__(self) -> str:
        """Provides a developer-friendly representation of the node."""
        return f"<{self.__class__.__name__} id={self._node_id}>"

    def add_child_node(self, child_node):
        # This check is critical for node sharing. It ensures that a parent node
        # doesn't have duplicate pointers to the same shared child node.
        if child_node not in self.child_nodes:
            self.child_nodes.append(child_node)

    @abstractmethod
    def insert(self, tuple_):
        """Processes the insertion of a single tuple."""
        pass

    @abstractmethod
    def retract(self, tuple_):
        """Processes the retraction of a single tuple."""
        pass

    def calculate_downstream(self, tuples):
        """Propagates inserted or updated tuples to all child nodes."""
        for child in self.child_nodes:
            for t in tuples:
                child.insert(t)

    def retract_downstream(self, tuples):
        """Propagates retracted tuples to all child nodes."""
        for child in self.child_nodes:
            for t in tuples:
                child.retract(t)

