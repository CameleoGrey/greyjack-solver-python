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
Strange problem. Different papers "lose" some coefficients, have different formulations.

links:
https://www.researchgate.net/publication/352203707_Enhanced_grasshopper_optimization_algorithm_using_elite_opposition-based_learning_for_solving_real-world_engineering_problems
https://www.sci-hub.ru/10.1016/j.cie.2021.107250
"""

if __name__ == "__main__":
    m = math_model = MathModel()

    m.variables["t"] = FloatVar(1.5, 3)
    m.variables["r_o"] = IntegerVar(90, 110)
    m.variables["r_i"] = IntegerVar(60, 80)
    m.variables["F"] = IntegerVar(600, 1000)
    m.variables["Z"] = IntegerVar(2, 9)

    m.utility["n"] = 250 #rpm
    m.utility["M_f"] = 3 #Nm
    m.utility["M_s"] = 40 #Nm
    m.utility["I_z"] = 55 #kg/m^2
    m.utility["dr"] = 20 #mm
    m.utility["t_min"] = 1.5 #mm
    m.utility["t_max"] = 3 #mm
    m.utility["l_max"] = 30 #mm
    m.utility["Z_max"] = 9
    m.utility["v_sr_max"] = 10 #m/s
    m.utility["nu"] = 0.5
    m.utility["delta"] = 0.5
    m.utility["p_max"] = 1 #MPa
    m.utility["T_max"] = 15 #s
    m.utility["F_max"] = 1000 #N
    m.utility["r_i_min"] = 60 #mm
    m.utility["r_i_max"] = 80 #mm
    m.utility["r_o_min"] = 90 #mm
    m.utility["r_o_max"] = 110 #mm
    m.utility["ro"] = 7.8e-6
    m.utility["s"] = 1.5
    m.utility["M_h"] = lambda v, u: ((2 / 3) * u["nu"] * v["F"] * v["Z"] * (v["r_o"]**3 - v["r_i"]**3)) / (v["r_o"]**2 - v["r_i"]**2)
    m.utility["p_rz"] = lambda v, u: v["F"] / (pi * (v["r_o"]**2 - v["r_i"]**2))
    m.utility["v_sr"] = lambda v, u: (2 * pi * ((v["r_o"]**3 - v["r_i"]**3)) / (90 * (v["r_o"]**2 - v["r_i"]**2)))
    m.utility["T"] = lambda v, u: (u["I_z"] * pi * u["n"]) / (30 * (u["M_h"](v, u) + u["M_f"]))

    m.objectives["f"] = Objective("minimize", lambda v, u: pi*v["t"]*u["ro"]*(v["r_o"]**2 - v["r_i"]**2)*(v["Z"] + 1))

    m.constraints["g_1"] = Constraint( lambda v, u: v["r_o"] - v["r_i"] - u["dr"], ">=")
    m.constraints["g_2"] = Constraint( lambda v, u: u["l_max"] - (v["Z"]+1)*(v["t"]+u["delta"]), ">=")
    m.constraints["g_3"] = Constraint( lambda v, u: u["p_max"] + u["p_rz"](v, u), ">=")
    m.constraints["g_4"] = Constraint( lambda v, u: u["p_max"]*u["v_sr_max"] - u["p_rz"](v, u)*u["v_sr"](v, u), ">=")
    m.constraints["g_5"] = Constraint( lambda v, u: u["v_sr_max"] - u["v_sr"](v, u), ">=")
    m.constraints["g_6"] = Constraint( lambda v, u: u["T_max"] - u["T"](v, u), ">=")
    m.constraints["g_7"] = Constraint( lambda v, u: u["M_h"](v, u) - u["s"]*u["M_s"], ">=")
    m.constraints["g_8"] = Constraint( lambda v, u: u["T"](v, u), ">=")

    termination_strategy = ScoreNoImprovement(time_seconds_limit=5)
    agent = GeneticAlgorithm(population_size=256, crossover_probability=0.8, p_best_rate=0.5,
                             tabu_entity_rate=0.2, mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                             migration_rate=0.00001, migration_frequency=10, termination_strategy=termination_strategy)
    
    solver = SolverPureMath(math_model, agent,
                            ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                            n_jobs=10, score_precision=[4, 2])
    solution = solver.solve()
    math_model.explain_solution( solution )

    print( solution )
    print( "done" )