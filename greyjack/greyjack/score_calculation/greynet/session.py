from __future__ import annotations

from .core.tuple_pool import TuplePool

class Session:
    def __init__(self, from_nodes, scoring_nodes, scheduler, score_class, tuple_pool: TuplePool, weights=None):
        self.from_nodes = from_nodes
        self.scoring_nodes = scoring_nodes
        self.scheduler = scheduler
        self.score_class = score_class
        self.fact_id_to_tuple = {}
        self.tuple_pool = tuple_pool
        self.weights = weights
        self._scoring_node_map = {node.constraint_id: node for node in scoring_nodes}

    def insert(self, fact):
        """Inserts a single fact and immediately processes the consequences."""
        self.insert_batch([fact])
        self.flush()

    def retract(self, fact):
        """Retracts a single fact and immediately processes the consequences."""
        self.retract_batch([fact])
        self.flush()

    def insert_batch(self, facts):
        """Inserts a collection of facts into the network."""

        for fact in facts:
            fact_type = type(fact)
            if fact_type not in self.from_nodes:
                continue
            
            fact_id = fact.greynet_fact_id
            if fact_id in self.fact_id_to_tuple:
                continue
            
            from_node = self.from_nodes[fact_type]
            tuple_ = from_node.insert(fact)
            self.fact_id_to_tuple[fact_id] = tuple_

    def retract_batch(self, facts):
        """Retracts a collection of facts from the network."""

        for fact in facts:
            fact_id = fact.greynet_fact_id
            tuple_ = self.fact_id_to_tuple.pop(fact_id, None)
            if tuple_ is None:
                continue

            tuple_.node.retract(tuple_)

    def flush(self):
        """Processes all pending changes in the scheduler queue."""
        self.scheduler.fire_all()
    
    def clear(self):
        """
        Retracts all known facts from the session and flushes the network.
        This effectively resets the session's state and releases all tuple
        objects back to the pool.
        """
        all_tuples = list(self.fact_id_to_tuple.values())
        
        for tuple_ in all_tuples:
            tuple_.node.retract(tuple_)
        
        self.fact_id_to_tuple.clear()
        
        self.flush()

    def update_constraint_weight(self, constraint_id: str, new_weight: float):
        """
        Updates the weight for a constraint and triggers an immediate recalculation
        of scores for all existing matches of that constraint.
        """
        if self.weights is None:
            raise RuntimeError("Cannot update weights. Session was not initialized with a weights manager.")
        if constraint_id not in self._scoring_node_map:
            raise ValueError(f"No constraint found with ID: '{constraint_id}'")

        self.weights.set_weight(constraint_id, new_weight)

        scoring_node = self._scoring_node_map[constraint_id]
        
        scoring_node.recalculate_scores()

    def get_score(self):
        """
        Flushes all pending changes and calculates the total score.
        Returns a score object (e.g., SimpleScore, HardSoftScore).
        """
        self.flush()

        total_score = self.score_class.get_null_score()
        for node in self.scoring_nodes:
            total_score += node.get_total_score()
        return total_score

    def get_constraint_matches(self):
        """
        Flushes all pending changes and returns a detailed breakdown of
        all constraint violations.
        """
        self.flush()
        matches = {}
        for node in self.scoring_nodes:
            if node.matches:
                matches[node.constraint_id] = list(node.matches.values())
        return matches

    def recalculate_all_scores(self):
        """
        Forces a recalculation of all scores for all active constraint matches.

        This is a lightweight recovery method ideal for scenarios where external factors,
        like constraint weights, have changed. It does not re-evaluate the network's
        joins or filters; it only re-runs the final impact function for each
        existing match.
        """
        for node in self.scoring_nodes:
            node.recalculate_scores()