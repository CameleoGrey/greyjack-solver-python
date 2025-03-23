from pathlib import Path
import os
import sys

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))


from greyjack.pure_math.MathModel import MathModel
from greyjack.pure_math.Objective import Objective
from greyjack.pure_math.Constraint import Constraint
from greyjack.pure_math.variables.IntegerVar import IntegerVar
import random
import numpy as np


def all_different(v, u):
    N = u["N"]
    row_ids = np.array([v[i] for i in u["ids"]])
    column_ids = u["column_ids"]
    penalty = 3*N - (np.unique(row_ids).shape[0] + np.unique(row_ids + column_ids).shape[0] + np.unique(row_ids - column_ids).shape[0])
    return penalty

def build_math_model(N, random_seed=45):

    m = model = MathModel()

    random.seed(random_seed)
    random_row_ids = list(range(N))
    random.shuffle( random_row_ids )

    m.utility["N"] = N
    m.utility["ids"] = []
    m.utility["column_ids"] = np.arange(0, N)
    for i in range(N):
        m.utility["ids"].append(str(i))
        m.variables[str(i)] = IntegerVar(0, N-1, random_row_ids[i])
    
    #m.constraints["unique_queens"] = Constraint(lambda v, u: len(set([v[i] for i in u["ids"]])), "==", lambda v, u: u["N"])
    #m.constraints["different_descend_ids"] = Constraint(lambda v, u: len(set([v[id] + i for i, id in enumerate(u["ids"])])), "==", lambda v, u: u["N"])
    #m.constraints["different_ascend_ids"] = Constraint(lambda v, u: len(set([v[id] - i for i, id in enumerate(u["ids"])])), "==", lambda v, u: u["N"])

    # alternative, can you do the same in classical solvers?
    m.constraints["all_different"] = Constraint(all_different, "==", lambda v, u: 0)

    m.objectives["f"] = Objective("minimize", lambda v, u: 0)
    
    return m

from greyjack.SolverPureMath import SolverPureMath
from greyjack.agents import *
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.termination_strategies import *

if __name__ == "__main__":

    N = 1024
    math_model = build_math_model(N, random_seed=45)

    #termination_strategy = StepsLimit(step_count_limit=1)
    #termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    #termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    termination_strategy = ScoreLimit(score_to_compare=[0, 0])
    agent = TabuSearch(neighbours_count=128, tabu_entity_rate=0.0, 
                       mutation_rate_multiplier=None, move_probas=[0.0, 1.0, 0, 0, 0, 0], 
                       migration_frequency=10, termination_strategy=termination_strategy)
    """agent = GeneticAlgorithm(population_size=128, crossover_probability=0.5, p_best_rate=0.05,
                             tabu_entity_rate=0.0, mutation_rate_multiplier=1.0, move_probas=[0, 1, 0, 0, 0, 0],
                             migration_rate=0.00001, migration_frequency=1, termination_strategy=termination_strategy)"""
    """agent = LateAcceptance(late_acceptance_size=10, tabu_entity_rate=0.0, 
                           mutation_rate_multiplier=None, move_probas=[0, 1, 0, 0, 0, 0], 
                           compare_to_global_frequency=1, termination_strategy=termination_strategy)"""
    """agent = SimulatedAnnealing(initial_temperature=[1.0], cooling_rate=0.9999, tabu_entity_rate=0.0, 
                               mutation_rate_multiplier=None, move_probas=[0, 1, 0, 0, 0, 0], 
                               migration_frequency=10, compare_to_global_frequency=10, termination_strategy=termination_strategy)"""
    
    solver = SolverPureMath(math_model, agent,
                            ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                            n_jobs=10, score_precision=[0, 0])
    solution = solver.solve()
    math_model.explain_solution( solution )


    # print chess board
    """column_ids = math_model.utility["column_ids"]
    row_ids = []
    for col_id in column_ids:
        row_id = solution.variable_values_dict[str(col_id)]
        row_ids.append(row_id)

    field_string = []
    for i in range(N):
        row_string = []
        for j in range(N):
            row_string.append( "-" )
        row_string.append("\n")
        field_string.append(row_string)

    for i in range(N):
        field_string[row_ids[i]][column_ids[i]] = "+"

    for i in range(N):
        row_string = field_string[i]
        row_string = " ".join( row_string )
        field_string[i] = row_string
    field_string = " ".join(field_string)
    field_string = " " + field_string
    print(field_string)"""

    print( "done" )