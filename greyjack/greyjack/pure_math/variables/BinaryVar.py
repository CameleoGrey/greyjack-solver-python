



class BinaryVar:

    """
    This is proxy variable, to make MathModel pickle'ble (necessary for parallel computation)
    GJVars replace proxy variables during agents initialization before solving
    """

    def __init__(self, initial_value=None, frozen=False, semantic_groups=None):

        self.frozen = frozen
        self.initial_value = initial_value
        self.semantic_groups = semantic_groups

        pass