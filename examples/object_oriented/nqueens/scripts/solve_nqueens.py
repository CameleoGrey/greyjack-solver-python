from pathlib import Path
import os
import sys

# To launch normally from console without setup.py greyjack (just for developing)
# Inside console run from from project dir: >python ./{path_to_example_script.py}
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from examples.object_oriented.nqueens.persistence.DomainBuilderNQueens import DomainBuilderNQueens
from examples.object_oriented.nqueens.persistence.CotwinBuilderNQueens import CotwinBuilderNQueens
from greyjack.agents.termination_strategies import *
from greyjack.agents import *
from greyjack.Solver import Solver
from greyjack.agents.TabuSearch import TabuSearch
from greyjack.agents.GeneticAlgorithm import GeneticAlgorithm

if __name__ == "__main__":

    # build domain model
    domain_builder = DomainBuilderNQueens(1024, random_seed=45)
    cotwin_builder = CotwinBuilderNQueens()

    #termination_strategy = StepsLimit(step_count_limit=1000)
    termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    #termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    #termination_strategy = ScoreLimit(score_to_compare=[0])
    agent = TabuSearch(neighbours_count=20, tabu_entity_rate=0.0, 
                       mutation_rate_multiplier=None, move_probas=[0, 1, 0, 0, 0, 0], 
                       migration_frequency=1, termination_strategy=termination_strategy)
    """agent = GeneticAlgorithm(population_size=128, crossover_probability=0.5, p_best_rate=0.05,
                             tabu_entity_rate=0.0, mutation_rate_multiplier=1.0, move_probas=[0, 1, 0, 0, 0, 0],
                             migration_rate=0.00001, migration_frequency=1, termination_strategy=termination_strategy)"""

    solver = Solver(domain_builder, cotwin_builder, agent, 
                    n_jobs=10, parallelization_backend="processing", #processing, threading 
                    score_precision=[0], logging_level="info")
    solution = solver.solve()
    #print( "Cotwin solution looks that: " )
    #print( solution )

    print( "done" )