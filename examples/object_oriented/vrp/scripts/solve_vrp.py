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

from examples.object_oriented.vrp.persistence.DomainBuilder import DomainBuilder
from examples.object_oriented.vrp.persistence.CotwinBuilder import CotwinBuilder
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.termination_strategies import *
from greyjack.Solver import Solver
from greyjack.agents import *

if __name__ == "__main__":

    # OptaPlanner/VRPLIB datasets and corresponding achieved results
    # Paths are relative to ${workspaceFolder}
    dir_path = os.path.dirname(os.path.realpath(__file__))
    data_dir_path = Path(project_dir_path, "data", "vrp", "data", "import")
    # 1-depot datasets (plain CVRP)
    #file_path = Path(data_dir_path, "vrpweb", "basic", "air", "A-n32-k5.vrp")
    #file_path = Path(data_dir_path, "vrpweb", "basic", "air", "F-n135-k7.vrp")
    #file_path = Path(data_dir_path, "usa", "basic", "air", "usa-n100-k10.vrp")
    #file_path = Path(data_dir_path, "belgium", "basic", "air", "belgium-n50-k10.vrp")
    #file_path = Path(data_dir_path, "belgium", "basic", "air", "belgium-n500-k20.vrp")
    #file_path = Path(data_dir_path, data_dir_path, "belgium", "basic", "air", "belgium-n1000-k40.vrp") #optimum: ~57.7; first_fit: ~195.3; RoutingModel: from 67.3 to 74 (depends on time)
    # multi-depot with timewindows
    #file_path = Path(data_dir_path, "belgium", "multidepot-timewindowed", "air", "belgium-tw-d2-n50-k10.vrp") # optimum: ~15.98; first_fit: ~27.89
    file_path = Path(data_dir_path, "belgium", "multidepot-timewindowed", "air", "belgium-tw-d5-n500-k20.vrp") # optimum: ~43.3; first_fit: ~124.884
    #file_path = Path(data_dir_path, "belgium", "multidepot-timewindowed", "air", "belgium-tw-d8-n1000-k40.vrp") # optimum: ~58.1; first_fit: ~154.565
    #file_path = Path(data_dir_path, "belgium", "multidepot-timewindowed", "air", "belgium-tw-d10-n2750-k55.vrp") # optimum: ~111; first_fit: ~380.9

    domain_builder = DomainBuilder(file_path)
    cotwin_builder = CotwinBuilder()
    cotwin = CotwinBuilder()

    #termination_strategy = StepsLimit(step_count_limit=1000)
    #termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    #termination_strategy = ScoreLimit(score_to_compare=[0])
    agent = TabuSearch(neighbours_count=128, tabu_entity_rate=0.2, 
                       mutation_rate_multiplier=None, move_probas=[0.5, 0.5, 0, 0, 0, 0],
                       migration_frequency=10, termination_strategy=termination_strategy)
    """agent = GeneticAlgorithm(population_size=128, crossover_probability=0.5, p_best_rate=0.05,
                             tabu_entity_rate=0.2, mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0, 0, 0, 0],
                             migration_rate=0.00001, migration_frequency=10, termination_strategy=termination_strategy)"""
    """agent = LateAcceptance(late_acceptance_size=20, tabu_entity_rate=0.2, 
                           mutation_rate_multiplier=None, move_probas=[0.5, 0.5, 0, 0, 0, 0], 
                           migration_frequency=1000, termination_strategy=termination_strategy)"""

    solver = Solver(domain_builder, cotwin_builder, agent, 
                    ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                    n_jobs=10, score_precision=[0, 0])
    solution = solver.solve()

    domain = domain_builder.build_from_solution(solution)
    domain.print_metrics()
    domain.print_paths()
    domain.plot_paths()

    print("done")
