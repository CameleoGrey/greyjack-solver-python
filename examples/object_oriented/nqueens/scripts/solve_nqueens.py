from pathlib import Path
import os
import sys

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from examples.object_oriented.nqueens.persistence.DomainBuilderNQueens import DomainBuilderNQueens
from examples.object_oriented.nqueens.persistence.CotwinBuilderNQueens import CotwinBuilderNQueens
from greyjack.agents.termination_strategies import *
from greyjack.agents import *
from greyjack.Solver import Solver
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents import *

if __name__ == "__main__":

    # build domain model
    domain_builder = DomainBuilderNQueens(10000, random_seed=45)
    cotwin_builder = CotwinBuilderNQueens(use_incremental_score_calculator=True)

    #termination_strategy = StepsLimit(step_count_limit=1000)
    termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    #termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    #termination_strategy = ScoreLimit(score_to_compare=[0])
    agent = TabuSearch(neighbours_count=20, tabu_entity_rate=0.0, 
                       mutation_rate_multiplier=None, move_probas=[0, 1, 0, 0, 0, 0], 
                       compare_to_global=True, migration_frequency=10, termination_strategy=termination_strategy)
    """agent = GeneticAlgorithm(population_size=128, crossover_probability=0.5, p_best_rate=0.05,
                             tabu_entity_rate=0.0, mutation_rate_multiplier=1.0, move_probas=[0, 1, 0, 0, 0, 0],
                             migration_rate=0.00001, migration_frequency=1, termination_strategy=termination_strategy)"""
    """agent = LateAcceptance(late_acceptance_size=10, tabu_entity_rate=0.0, 
                           mutation_rate_multiplier=None, move_probas=[0, 1, 0, 0, 0, 0], 
                           termination_strategy=termination_strategy)"""
    """agent = SimulatedAnnealing(initial_temperature=[1.0], cooling_rate=0.9999, tabu_entity_rate=0.0, 
                               mutation_rate_multiplier=None, move_probas=[0, 1, 0, 0, 0, 0], 
                               compare_to_global=True, migration_frequency=10, termination_strategy=termination_strategy)"""

    solver = Solver(domain_builder, cotwin_builder, agent, 
                    ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                    n_jobs=10, score_precision=[0])
    solution = solver.solve()
    #print( "Cotwin solution looks that: " )
    #print( solution )

    print( "done" )