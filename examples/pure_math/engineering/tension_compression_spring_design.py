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


from copy import deepcopy

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

"""
https://www.sci-hub.ru/10.1016/j.cie.2021.107250
"""

if __name__ == "__main__":
    m = math_model = MathModel()

    m.variables["x1"] = FloatVar( 0.05, 2.0 )
    m.variables["x2"] = FloatVar( 0.25, 1.3 )
    m.variables["x3"] = FloatVar( 2.0, 15.0 )

    # optimum objective in https://ceur-ws.org/Vol-2255/paper2.pdf is 0.0126652327883
    m.objectives["f"] = Objective("minimize", lambda v, u: (v["x3"] + 2)*v["x2"]*(v["x1"]**2))

    m.constraints["g1"] = Constraint( lambda v, u: 1 - v["x2"]**3*v["x3"]/(71785*v["x1"]**4), "<=")
    # in the article about Aquila authors lost "-1" in the end of "g2" constraint...
    m.constraints["g2"] = Constraint( lambda v, u: (4*v["x2"]**2 - v["x1"]*v["x2"]) / (12566*(v["x2"]*v["x1"]**3 - v["x1"]**4)) + (1/(5108*v["x1"]**2)) - 1, "<=")
    m.constraints["g3"] = Constraint( lambda v, u: 1 - (140.45*v["x1"])/(v["x2"]**2*v["x3"]), "<=")
    m.constraints["g4"] = Constraint( lambda v, u: (v["x1"] + v["x2"])/1.5 - 1, "<=")

    termination_strategy = ScoreNoImprovement(time_seconds_limit=5)
    agent = GeneticAlgorithm(population_size=256, crossover_probability=0.8, p_best_rate=0.5,
                             tabu_entity_rate=0.2, mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                             migration_rate=0.00001, migration_frequency=10, termination_strategy=termination_strategy)
    
    solver = SolverPureMath(math_model, agent,
                            ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                            n_jobs=10, score_precision=[4, 2])
    solution = solver.solve()

    m.variables["x1"] = solution.variable_values_dict["x1"]
    m.variables["x2"] = solution.variable_values_dict["x2"]
    m.variables["x3"] = solution.variable_values_dict["x3"]
    print( "Optimal values from GreyJack" )
    math_model.explain_solution( solution )
    print()

    # optimal values from Aquila article
    solution.variable_values_dict["x1"] = 0.0502439
    solution.variable_values_dict["x2"] = 0.35262
    solution.variable_values_dict["x3"] = 10.5425
    print( "Optimal values from article about Aquila" )
    math_model.explain_solution( solution )
    print()

    # optimal values from https://ceur-ws.org/Vol-2255/paper2.pdf
    solution.variable_values_dict["x1"] = 0.051689156131
    solution.variable_values_dict["x2"] = 0.356720026419
    solution.variable_values_dict["x3"] = 11.288831695483
    print( "Optimal values from https://ceur-ws.org/Vol-2255/paper2.pdf" )
    math_model.explain_solution( solution )

    print( "done" )