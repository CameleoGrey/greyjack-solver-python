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

    # OptaPlanner/TSPLIB datasets and corresponding achieved results
    data_dir_path = Path(project_dir_path, "data", "tsp", "data", "import")
    #file_path = Path(data_dir_path, "cook", "air", "dj38.tsp") # 6659 - optimum
    #file_path = Path(data_dir_path, "belgium", "air", "belgium-n50.tsp") # ~12.2 - optimum
    #file_path = Path(data_dir_path, "cook", "air", "st70.tsp") # 682.57 - optimum
    #file_path = Path(data_dir_path, "belgium", "road-km", "belgium-road-km-n100.tsp") # 1727.262 - optimum, 2089 - first_fit
    #file_path = Path(data_dir_path, "tsplib", "a280.tsp") # 2579 - optimal
    file_path = Path(data_dir_path, "cook", "air", "pcb442.tsp") #optimum: 50778; first_fit: ~63k
    #file_path = Path(data_dir_path, "cook", "air", "lu980.tsp")
    #file_path = Path(data_dir_path, "other", "air", "usa_tx_2743.tsp") #optimum: ~282; first_fit: ~338
    #file_path = Path(data_dir_path, "belgium", "air", "belgium-n2750.tsp")
    #file_path = Path(data_dir_path, "tsplib", "fnl4461.tsp") #optimum: 182566; first_fit: ~230k
    #file_path = Path(data_dir_path, "cook", "air", "gr9882.tsp") #optimum: 300899; first_fit: ~400k

    domain_builder = DomainBuilder(file_path)
    cotwin_builder = CotwinBuilder(use_incremental_score_calculator=True)

    #termination_strategy = StepsLimit(step_count_limit=1000)
    termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    #termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    #termination_strategy = ScoreLimit(score_to_compare=[0])
    agent = TabuSearch(neighbours_count=128, tabu_entity_rate=0.5, 
                       mutation_rate_multiplier=None, move_probas=[0.0, 0.2, 0.2, 0.2, 0.2, 0.2],
                       migration_frequency=10, termination_strategy=termination_strategy)
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
                    ParallelizationBackend.Multiprocessing, LoggingLevel.Info,
                    n_jobs=10, score_precision=[0, 0])
    solution = solver.solve()

    domain = domain_builder.build_from_solution(solution)
    domain.print_metrics()
    domain.print_path()
    #domain.plot_path()

    print("done")
