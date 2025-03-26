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

    for i in range( 1, 6 ): 
        m.variables[f"x{i}"] = FloatVar( 0.01, 100 )
    m.objectives["f"] = Objective("minimize", lambda v, u: 0.06224*sum([x_i for x_i in v.values()]))
    m.constraints["g"] = Constraint( lambda v, u: 60/v["x1"]**3 + 27/v["x2"]**3 + 19/v["x3"]**3 + 7/v["x4"]**3 + 1/v["x5"]**3 - 1, "<=")

    termination_strategy = ScoreNoImprovement(time_seconds_limit=5)
    agent = GeneticAlgorithm(population_size=256, crossover_probability=0.8, p_best_rate=0.5,
                             tabu_entity_rate=0.2, mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                             migration_rate=0.00001, migration_frequency=10, termination_strategy=termination_strategy)
    """agent = LateAcceptance(late_acceptance_size=200, tabu_entity_rate=0.2, 
                           mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                           compare_to_global_frequency=10000, termination_strategy=termination_strategy)"""
    
    solver = SolverPureMath(math_model, agent,
                            ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                            n_jobs=10, score_precision=[4, 2])
    solution = solver.solve()
    math_model.explain_solution( solution )

    print( solution )
    print( "done" )