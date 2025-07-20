from ..nodes.abstract_node import AbstractNode
class ScoringNode(AbstractNode):
    def __init__(self, node_id, constraint_id, impact_function, score_class):
        super().__init__(node_id)
        self.constraint_id = constraint_id
        self.impact_function = impact_function
        self.score_class = score_class
        self.matches = {}
    
    def __repr__(self) -> str:
        """Overrides base representation to show the constraint ID."""
        return f"<{self.__class__.__name__} id={self._node_id} constraint_id='{self.constraint_id}'>"


    def insert(self, tuple_):
        args = [f for f in (
            getattr(tuple_, 'fact_a', None),
            getattr(tuple_, 'fact_b', None),
            getattr(tuple_, 'fact_c', None),
            getattr(tuple_, 'fact_d', None),
            getattr(tuple_, 'fact_e', None)
        ) if f is not None]

        score_object = self.impact_function(*args)

        if not isinstance(score_object, self.score_class):
            raise TypeError(
                f"Impact function for constraint '{self.constraint_id}' "
                f"returned type {type(score_object).__name__}, but session "
                f"is configured for {self.score_class.__name__}."
            )
        
        match = (score_object, tuple_)
        self.matches[tuple_] = match

    def retract(self, tuple_):
        if tuple_ in self.matches:
            del self.matches[tuple_]

    def recalculate_scores(self):
        """
        Iterates over all existing matches and re-calculates their score.
        """
        for tuple_ in list(self.matches.keys()):
            args = [f for f in (
                getattr(tuple_, 'fact_a', None),
                getattr(tuple_, 'fact_b', None),
                getattr(tuple_, 'fact_c', None),
                getattr(tuple_, 'fact_d', None),
                getattr(tuple_, 'fact_e', None)
            ) if f is not None]

            new_score_object = self.impact_function(*args)
            self.matches[tuple_] = (new_score_object, tuple_)

    def get_total_score(self):
        total = self.score_class.get_null_score()
        for score, _ in self.matches.values():
            total += score
        return total
