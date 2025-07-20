# greynet/optimization/node_sharing.py
from __future__ import annotations
from typing import Dict, Any

class NodeSharingManager:
    """
    Manages the creation and sharing of nodes within the Rete network.

    This class holds maps for different types of nodes (alpha, beta, etc.)
    and ensures that if a node with an identical definition is requested,
    the existing instance is returned instead of creating a new one.
    This is the core of the node sharing optimization.
    """
    def __init__(self):
        # A map for each category of shareable node.
        # The key is the stream's unique `retrieval_id`.
        # The value is the created node instance.
        self.alpha_nodes: Dict[Any, Any] = {}
        self.beta_nodes: Dict[Any, Any] = {}
        self.group_nodes: Dict[Any, Any] = {}
        self.temporal_nodes: Dict[Any, Any] = {}
        # Other node types like 'from' or 'scoring' are typically not shared
        # as they are entry/exit points for a specific rule or fact type.

    def get_or_create_node(self, retrieval_id: Any, node_map: Dict, node_supplier: callable):
        """
        Generic factory method to get an existing node or create a new one.

        Args:
            retrieval_id: The unique identifier for the stream/node definition.
            node_map (Dict): The specific dictionary to check (e.g., self.alpha_nodes).
            node_supplier (callable): A function that creates and returns a new node instance.

        Returns:
            A shared node instance.
        """
        node = node_map.get(retrieval_id)
        if node is None:
            node = node_supplier()
            node_map[retrieval_id] = node
        return node
