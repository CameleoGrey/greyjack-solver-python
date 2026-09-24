from copy import deepcopy
from pathlib import Path
import os
import sys

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from examples.object_oriented.tsp.persistence import DomainBuilder
from examples.object_oriented.tsp.persistence import CotwinBuilder
from greyjack.agents.termination_strategies import *
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack import SolverOOP
from greyjack.agents import *

if __name__ == "__main__":

    # Checked-in OptaPlanner/TSPLIB datasets
    data_dir_path = Path(project_dir_path, "data", "tsp")
    #file_path = Path(data_dir_path, "dj38.tsp") # 6659 - optimum
    #file_path = Path(data_dir_path, "belgium-n50.tsp") # ~12.2 - optimum
    #file_path = Path(data_dir_path, "st70.tsp") # 682.57 - optimum
    #file_path = Path(data_dir_path, "belgium-n100.tsp")
    file_path = Path(data_dir_path, "pcb442.tsp") #optimum: 50778; first_fit: ~63k
    #file_path = Path(data_dir_path, "belgium-n500.tsp")
    #file_path = Path(data_dir_path, "lu980.tsp")
    #file_path = Path(data_dir_path, "belgium-n1000.tsp")
    #file_path = Path(data_dir_path, "belgium-n2750.tsp")
    #file_path = Path(data_dir_path, "gr9882.tsp") #optimum: 300899; first_fit: ~400k
    #file_path = Path(data_dir_path, "ch71009.tsp")
    #file_path = Path(data_dir_path, "usa115475.tsp")

    domain_builder = DomainBuilder(file_path)
    cotwin_builder = CotwinBuilder(use_incremental_score_calculator=True)

    #termination_strategy = StepsLimit(step_count_limit=1000)
    #termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    #termination_strategy = ScoreLimit(score_to_compare=[0])
    agent = TabuSearch(neighbours_count=128, tabu_entity_rate=0.5, 
                       mutation_rate_multiplier=None, move_probas=[0.0, 0.2, 0.2, 0.2, 0.2, 0.2],
                       migration_frequency=99999999, compare_to_global_frequency=10, 
                       termination_strategy=termination_strategy)
    """agent = GeneticAlgorithm(population_size=128, crossover_probability=0.5, p_best_rate=0.05,
                             tabu_entity_rate=0.2, mutation_rate_multiplier=1.0, move_probas=[0.0, 0.2, 0.2, 0.2, 0.2, 0.2],
                             migration_rate=0.00001, migration_frequency=10, termination_strategy=termination_strategy)"""
    """agent = LateAcceptance(late_acceptance_size=64, tabu_entity_rate=0.2, 
                           mutation_rate_multiplier=None, move_probas=[0.0, 0.2, 0.2, 0.2, 0.2, 0.2], 
                           termination_strategy=termination_strategy)"""
    """agent = SimulatedAnnealing(initial_temperature=[1.0, 1.0], cooling_rate=0.9999, tabu_entity_rate=0.2, 
                               mutation_rate_multiplier=None, move_probas=[0, 0.2, 0.2, 0.2, 0.2, 0.2], 
                               migration_frequency=10, termination_strategy=termination_strategy)"""

    solver = SolverOOP(domain_builder, cotwin_builder, agent, 
                    ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                    n_jobs=10, score_precision=[0, 0])
    solution = solver.solve()

    domain = domain_builder.build_from_solution(solution)
    domain.print_metrics()
    domain.print_path()
    domain.plot_path()

    print("done")
