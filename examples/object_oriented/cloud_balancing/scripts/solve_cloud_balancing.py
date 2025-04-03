from copy import deepcopy
from pathlib import Path
import os
import sys

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from examples.object_oriented.cloud_balancing.persistence.DomainBuilder import DomainBuilder
from examples.object_oriented.cloud_balancing.persistence.CotwinBuilder import CotwinBuilder
from greyjack.agents.termination_strategies import *
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack import SolverOOP
from greyjack.agents import *

if __name__ == "__main__":

    # OptaPlanner/TSPLIB datasets and corresponding achieved results
    data_dir_path = Path(project_dir_path, "data", "cloudbalancing")
    #file_path = Path(data_dir_path, "4computers-12processes.json")
    #file_path = Path(data_dir_path, "100computers-300processes.json")
    #file_path = Path(data_dir_path, "200computers-600processes.json") 
    file_path = Path(data_dir_path, "400computers-1200processes.json") 
    #file_path = Path(data_dir_path, "800computers-2400processes.json") 
    #file_path = Path(data_dir_path, "1600computers-4800processes.json") 


    domain_builder = DomainBuilder(file_path)
    cotwin_builder = CotwinBuilder(use_incremental_score_calculator=True, use_greed_init=True)

    #termination_strategy = StepsLimit(step_count_limit=1000)
    #termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    #termination_strategy = ScoreLimit(score_to_compare=[0])
    agent = TabuSearch(neighbours_count=20, tabu_entity_rate=0.8, 
                       mutation_rate_multiplier=None, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                       migration_frequency=10, termination_strategy=termination_strategy)
    """agent = GeneticAlgorithm(population_size=128, crossover_probability=0.5, p_best_rate=0.2,
                             tabu_entity_rate=0.2, mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                             migration_rate=0.00001, migration_frequency=10, termination_strategy=termination_strategy)"""
    """agent = LateAcceptance(late_acceptance_size=5, tabu_entity_rate=0.8, 
                           mutation_rate_multiplier=None, compare_to_global_frequency=10, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                           termination_strategy=termination_strategy)"""
    """agent = SimulatedAnnealing(initial_temperature=[1.0, 1.0], cooling_rate=0.9999, tabu_entity_rate=0.8, 
                               mutation_rate_multiplier=None, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                               migration_frequency=10, compare_to_global_frequency=10, termination_strategy=termination_strategy)"""

    solver = SolverOOP(domain_builder, cotwin_builder, agent, 
                    ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                    n_jobs=10, score_precision=[0, 0, 0])
    solution = solver.solve()

    domain = domain_builder.build_from_solution(solution)
    domain.print_metrics()

    print("done")
