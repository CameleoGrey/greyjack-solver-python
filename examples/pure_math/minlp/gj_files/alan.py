# MINLP rewritten by GreyJack
#
# Equation counts
#     Total        E        G        L        N        X        C        B
#         7        2        0        5        0        0        0        0
#
# Variable counts
#                  x        b        i      s1s      s2s       sc       si
#     Total     cont   binary  integer     sos1     sos2    scont     sint
#         8        4        4        0        0        0        0        0
# FX      0
#
# Nonzero counts
#     Total    const       NL
#        20       20        0
#

from math import pi, log, exp
from greyjack.pure_math.MathModel import MathModel
from greyjack.pure_math.Objective import Objective
from greyjack.pure_math.Constraint import Constraint
from greyjack.pure_math.variables.FloatVar import FloatVar
from greyjack.pure_math.variables.IntegerVar import IntegerVar
from greyjack.pure_math.variables.BinaryVar import BinaryVar

def build_math_model():

    m = model = MathModel()
    
    m.variables["x1"] = FloatVar(0, 1)
    m.variables["x2"] = FloatVar(0, 1)
    m.variables["x3"] = FloatVar(0, 1)
    m.variables["x4"] = FloatVar(0, 1 )
    m.variables["b5"] = BinaryVar( )
    m.variables["b6"] = BinaryVar( )
    m.variables["b7"] = BinaryVar( initial_value=0 )
    m.variables["b8"] = IntegerVar( 0, 1, initial_value=0 )
    
    m.objectives["f"] = Objective("minimize", lambda v, u: v["x1"] * (4 * v["x1"] + 3 * v["x2"] - v["x3"]) +v["x2"] * (3 * v["x1"] + 6 * v["x2"] + v["x3"]) + v["x3"] * (-v["x1"] + v["x2"] + 10 * v["x3"]))
    
    m.constraints["e1"] = Constraint(lambda v, u: v["x1"] + v["x2"] + v["x3"] + v["x4"], "==", lambda v, u: 1)
    m.constraints["e2"] = Constraint(lambda v, u: 8 * v["x1"] + 9 * v["x2"] + 12 * v["x3"] + 7 * v["x4"], "==", lambda v, u: 10)
    m.constraints["e3"] = Constraint(lambda v, u: v["x1"] - v["b5"], "<=", lambda v, u: 0)
    m.constraints["e4"] = Constraint(lambda v, u: v["x2"] - v["b6"], "<=", lambda v, u: 0)
    m.constraints["e5"] = Constraint(lambda v, u: v["x3"] - v["b7"], "<=", lambda v, u: 0)
    m.constraints["e6"] = Constraint(lambda v, u: v["x4"] - v["b8"], "<=", lambda v, u: 0)
    m.constraints["e7"] = Constraint(lambda v, u: v["b5"] + v["b6"] + v["b7"] + v["b8"], "<=", lambda v, u: 3)
    
    return m