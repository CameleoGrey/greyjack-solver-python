

#from greyjack.greyjack import GJPlanningVariable
from greyjack.greyjack import GJPlanningVariable
from greyjack.variables import GJFloat, GJInteger
from greyjack.score_requesters.OOPScoreRequester import OOPScoreRequester

if __name__ == "__main__":

    common_variable = GJPlanningVariable(name="x", lower_bound=0.0, upper_bound=1.0, is_int=False, frozen=False, initial_value=None, semantic_groups=None)
    print(common_variable.fix(-1))

    float_variable = GJFloat(name="x", lower_bound=10.0, upper_bound=100.0, frozen=False, initial_value=None, semantic_groups=None)
    print(float_variable.fix(1))

    float_variable = GJInteger(name="x", lower_bound=100.0, upper_bound=1000.0, frozen=False, initial_value=None, semantic_groups=None)
    print(float_variable.fix(10))

    print(OOPScoreRequester())

    print("done")
    