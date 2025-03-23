

class Objective():

    def __init__(self, optimization_direction, expression_lambda):
        self.optimization_direction = optimization_direction
        self.expression_lambda = expression_lambda

    def get_soft_score(self, variables, utility_objects, is_fitting):
        expression_lambda = self.expression_lambda
        soft_score = self._get_soft_score(expression_lambda, variables, utility_objects, self.optimization_direction, is_fitting)
        return soft_score

    @staticmethod
    def _get_soft_score(expression_lambda, variables, utility_objects, optimization_direction, is_fitting):
        soft_score = expression_lambda(variables, utility_objects)

        # the whole solver architecture specializes on minimization
        # if one needs maximize objective, one should invert objective value during solver training/fitting
        # but when one gets results for explanation, one needs the raw value without inverting
        if is_fitting:
            if optimization_direction in ["max", "maximize", "maximization"]:
                soft_score = -soft_score

        return soft_score
