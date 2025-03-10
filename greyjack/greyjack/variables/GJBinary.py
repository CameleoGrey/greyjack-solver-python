

from greyjack.greyjack import GJPlanningVariablePy


class GJBinary:

    def __init__(self, frozen, initial_value=None, semantic_groups=None):

        self.planning_variable = GJPlanningVariablePy(
            lower_bound = 0.0, 
            upper_bound = 1.0,
            frozen = frozen, 
            is_int = True, 
            initial_value = initial_value, 
            semantic_groups = semantic_groups,
        )

        pass