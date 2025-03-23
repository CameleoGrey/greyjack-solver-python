



class IntegerVar:

    """
    This is proxy variable, to make MathModel pickle'ble (necessary for parallel computation)
    GJVars replace proxy variables during agents initialization before solving
    """

    def __init__(self, lower_bound, upper_bound, initial_value=None, frozen=False, semantic_groups=None):

        assert lower_bound is not None
        assert upper_bound is not None

        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.frozen = frozen
        self.initial_value = initial_value
        self.semantic_groups = semantic_groups

        pass