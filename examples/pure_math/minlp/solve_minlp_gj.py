
from pathlib import Path
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
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.termination_strategies import *

from examples.pure_math.minlp.gj_files.sssd import *

if __name__ == "__main__":

    # for standard LP, QP problems fomulations better use classic solvers (they are specially made for them)
    # one needs metaheuristics, when classic solvers struggle, too difficult or just impossible to use:
    # (difficult functions, fast development, lack of expressiveness (explore OOP API of GreyJack Solver to 
    # understand how to express problems by another, much more comfort and easy way), adaptability to new requirements, clarity of 
    # processes during optimization, explainability, etc, etc)
    # here I use metaheuristics on standard LP, QP problems by using MathModel API just for benchmarks
    math_model = build_math_model()

    #termination_strategy = StepsLimit(step_count_limit=1000)
    #termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    #termination_strategy = ScoreLimit(score_to_compare=[0, 0])

    agent = LSHADE(population_size=128, history_archive_size=100, 
                   p_best_rate=0.2, tabu_entity_rate=0.2, 
                   mutation_rate_multiplier=1.0, move_probas=None,
                   memory_pruning_rate=0.0, guarantee_of_change_size=0, 
                   initial_f=0.5, initial_cr=0.02, initial_mutation_proba=0.5,
                   migration_rate=0.00001, migration_frequency=100, termination_strategy=termination_strategy)
    """agent = GeneticAlgorithm(population_size=256, crossover_probability=0.8, p_best_rate=0.5,
                             tabu_entity_rate=0.8, mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                             migration_rate=0.00001, migration_frequency=10, termination_strategy=termination_strategy)"""
    """agent = TabuSearch(neighbours_count=1000, tabu_entity_rate=0.8, 
                       mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                       compare_to_global_frequency=10, termination_strategy=termination_strategy)"""
    """agent = LateAcceptance(late_acceptance_size=200, tabu_entity_rate=0.8, 
                           mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                           compare_to_global_frequency=10000, termination_strategy=termination_strategy)"""
    """agent = SimulatedAnnealing(initial_temperature=[1.0, 1.0], cooling_rate=0.9999, tabu_entity_rate=0.8, 
                               mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                               compare_to_global_frequency=1000, termination_strategy=termination_strategy)"""
    
    solver = SolverPureMath(math_model, agent,
                            ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                            n_jobs=10, score_precision=[4, 2])
    solution = solver.solve()
    math_model.explain_solution( solution )

    print( "done" )