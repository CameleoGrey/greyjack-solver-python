from copy import deepcopy
from pathlib import Path
import random
import os
import sys

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from greyjack.SolverPureMath import SolverPureMath
from greyjack.agents import *
from greyjack.agents.termination_strategies import *
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents.base.LoggingLevel import LoggingLevel

from greyjack.pure_math.MathModel import MathModel
from greyjack.pure_math.Objective import Objective
from greyjack.pure_math.Constraint import Constraint
from greyjack.pure_math.variables.FloatVar import FloatVar
from greyjack.pure_math.variables.IntegerVar import IntegerVar
from greyjack.pure_math.variables.BinaryVar import BinaryVar

from copy import deepcopy
from math import pi

"""
https://www.sci-hub.ru/10.1016/j.cie.2021.107250
https://ceur-ws.org/Vol-2255/paper2.pdf
"""

if __name__ == "__main__":
    m = math_model = MathModel()

    m.variables["x1"] = FloatVar( 0, 99 )
    m.variables["x2"] = FloatVar( 0, 99 )
    m.variables["x3"] = FloatVar( 10, 200 )
    m.variables["x4"] = FloatVar( 10, 200 )

    # optimum objective in https://ceur-ws.org/Vol-2255/paper2.pdf is 0.0126652327883
    m.objectives["f"] = Objective("minimize",
                                lambda v, u: 0.6224*v["x1"]*v["x3"]*v["x4"] + 1.7781*v["x2"]*v["x3"]**2 +
                                            3.1661*v["x1"]**2*v["x4"] + 19.84*v["x1"]**2*v["x3"] )

    m.constraints["g1"] = Constraint( lambda v, u: -v["x1"] + 0.0193*v["x3"], "<=")
    m.constraints["g2"] = Constraint( lambda v, u: -v["x2"] + 0.00954*v["x3"], "<=")
    m.constraints["g3"] = Constraint( lambda v, u: -pi*v["x3"]**2*v["x4"] - (4/3)*pi*v["x3"]**3 + 1296000, "<=")
    m.constraints["g4"] = Constraint( lambda v, u: v["x4"] - 240, "<=")

    termination_strategy = ScoreNoImprovement(time_seconds_limit=5)
    """agent = GeneticAlgorithm(population_size=256, crossover_probability=0.8, p_best_rate=0.5,
                             tabu_entity_rate=0.2, mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                             migration_rate=0.00001, migration_frequency=10, termination_strategy=termination_strategy)"""
    agent = LateAcceptance(late_acceptance_size=200, tabu_entity_rate=0.2, 
                           mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                           compare_to_global_frequency=10000, termination_strategy=termination_strategy)
    
    solver = SolverPureMath(math_model, agent,
                            ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                            n_jobs=10, score_precision=[4, 2])
    solution = solver.solve()
    math_model.explain_solution( solution )

    print( solution )
    print( "done" )