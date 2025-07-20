# greynet/nodes/alpha_node.py
from ..nodes.abstract_node import AbstractNode

class AlphaNode(AbstractNode):
    """
    An AlphaNode represents a single, intra-element condition.
    It filters tuples based on a predicate applied to a single fact.
    This is the primary component of the Alpha Network.
    """
    def __init__(self, node_id, predicate, scheduler):
        super().__init__(node_id)
        self.predicate = predicate
        self.scheduler = scheduler
        # Alpha nodes do not need their own memory; they are simple pass-through filters.
        # The first BetaNode they connect to will serve as the memory.

    def insert(self, tuple_):
        """
        If the tuple's fact satisfies the predicate, it is propagated
        to all child nodes.
        """
        # The predicate operates on the fact contained within the tuple.
        if self.predicate(tuple_.fact_a):
            self.calculate_downstream([tuple_])

    def retract(self, tuple_):
        """
        If the tuple's fact satisfied the predicate, its retraction is
        propagated to all child nodes.
        """
        # The predicate must be re-evaluated to ensure symmetric retraction.
        if self.predicate(tuple_.fact_a):
            self.retract_downstream([tuple_])

