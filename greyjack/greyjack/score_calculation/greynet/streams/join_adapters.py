# greynet/streams/join_adapters.py
from __future__ import annotations
from typing import TYPE_CHECKING

from ..nodes.abstract_node import AbstractNode
from ..core.tuple import AbstractTuple

if TYPE_CHECKING:
    from ..nodes.beta_node import BetaNode


class JoinLeftAdapter(AbstractNode):
    """
    An adapter that redirects generic insert/retract calls to the 'left' inputs
    of a BetaNode (e.g., JoinNode, ConditionalNode).
    
    This allows a parent node to treat the BetaNode as a simple child, while the
    BetaNode can correctly distinguish between its left and right inputs.
    """
    def __init__(self, beta_node: 'BetaNode'):
        """
        Initializes the adapter.

        Args:
            beta_node: The beta node (e.g., JoinNode) to which calls will be redirected.
        """
        # Note: We don't call super().__init__() as this adapter does not need a node_id
        # and will never have its own children. It is a terminal pass-through.
        self.beta_node = beta_node
    
    def __repr__(self) -> str:
        """Provides a representation showing which node it adapts."""
        return f"<{self.__class__.__name__} for_node={self.beta_node!r}>"


    def insert(self, tuple_: AbstractTuple):
        """
        Receives a tuple from the parent (left) stream and passes it to the
        beta_node's insert_left method.
        """
        self.beta_node.insert_left(tuple_)

    def retract(self, tuple_: AbstractTuple):
        """
        Receives a retraction from the parent (left) stream and passes it to the
        beta_node's retract_left method.
        """
        self.beta_node.retract_left(tuple_)


class JoinRightAdapter(AbstractNode):
    """
    An adapter that redirects generic insert/retract calls to the 'right' inputs
    of a BetaNode (e.g., JoinNode, ConditionalNode).
    
    This allows a parent node to treat the BetaNode as a simple child, while the
    BetaNode can correctly distinguish between its left and right inputs.
    """
    def __init__(self, beta_node: 'BetaNode'):
        """
        Initializes the adapter.

        Args:
            beta_node: The beta node (e.g., JoinNode) to which calls will be redirected.
        """
        self.beta_node = beta_node
    
    def __repr__(self) -> str:
        """Provides a representation showing which node it adapts."""
        return f"<{self.__class__.__name__} for_node={self.beta_node!r}>"


    def insert(self, tuple_: AbstractTuple):
        """
        Receives a tuple from the parent (right) stream and passes it to the
        beta_node's insert_right method.
        """
        self.beta_node.insert_right(tuple_)

    def retract(self, tuple_: AbstractTuple):
        """
        Receives a retraction from the parent (right) stream and passes it to the
        beta_node's retract_right method.
        """
        self.beta_node.retract_right(tuple_)

