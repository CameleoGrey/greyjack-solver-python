

from greyjack.greyjack import GJPlanningVariablePy


class GJInteger:

    def __init__(self, lower_bound, upper_bound, frozen, initial_value=None, semantic_groups=None):

        self.planning_variable = GJPlanningVariablePy(
            lower_bound = lower_bound, 
            upper_bound = upper_bound, 
            frozen = frozen, 
            is_int = True, 
            initial_value = initial_value, 
            semantic_groups = semantic_groups,
        )

        pass