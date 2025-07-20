from ..streams.abstract_stream import AbstractStream
from ..nodes.scoring_node import ScoringNode

class ScoringStream(AbstractStream):
    def __init__(self, source_stream, constraint_id, impact_function):
        retrieval_id = ("score", constraint_id)
        super().__init__(source_stream.constraint_factory, retrieval_id)
        self.and_source(source_stream)
        self.constraint_id = constraint_id
        self.impact_function = impact_function

    def build_node(self, node_counter, node_map, scheduler, tuple_pool):
        node = node_map.get(self.retrieval_id)
        if node is None:
            source_node = self.source_stream.build_node(node_counter, node_map, scheduler, tuple_pool)
            node_id = node_counter.value
            node_counter.value += 1
            
            score_class = self.constraint_factory.score_class
            node = ScoringNode(node_id, self.constraint_id, self.impact_function, score_class)
            
            source_node.add_child_node(node)
            node_map[self.retrieval_id] = node
        return node
