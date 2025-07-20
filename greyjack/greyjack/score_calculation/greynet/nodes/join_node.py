from __future__ import annotations
from typing import Type
from .beta_node import BetaNode
from ..core.tuple import AbstractTuple
from ..tuple_tools import get_facts, get_arity

class JoinNode(BetaNode):
    """A generic beta node that joins two streams and creates a combined tuple."""
    def __init__(self, node_id, joiner_type, left_props, right_props, scheduler, tuple_pool, child_tuple_class: Type[AbstractTuple]):
        super().__init__(node_id, joiner_type, left_props, right_props, scheduler, tuple_pool)
        self.child_tuple_class = child_tuple_class
        # Pre-calculate the attribute names for the child tuple for performance
        self.child_fact_names = [f'fact_{chr(97+i)}' for i in range(get_arity(child_tuple_class))]

    def _create_child_tuple(self, left_tuple: AbstractTuple, right_tuple: AbstractTuple) -> AbstractTuple:
        """Creates a new tuple by combining the facts from the parent tuples."""
        combined_facts = get_facts(left_tuple) + get_facts(right_tuple)
        
        # Create a kwargs dictionary like {'fact_a': v1, 'fact_b': v2, ...}
        fact_kwargs = dict(zip(self.child_fact_names, combined_facts))

        return self.tuple_pool.acquire(
            self.child_tuple_class,
            **fact_kwargs
        )
