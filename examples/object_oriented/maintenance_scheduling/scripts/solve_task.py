from pathlib import Path
import os
import sys
import traceback

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from examples.object_oriented.maintenance_scheduling.persistence.DomainBuilder import DomainBuilder
from examples.object_oriented.maintenance_scheduling.persistence.CotwinBuilder import CotwinBuilder
from greyjack.agents.termination_strategies import *
from greyjack.agents import *
from greyjack.SolverOOP import SolverOOP
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents import *

if __name__ == "__main__":

    domain_builder = DomainBuilder(dataset_size="small")
    cotwin_builder = CotwinBuilder(use_incremental_score_calculator=True, use_greed_init=False)

    #termination_strategy = StepsLimit(step_count_limit=1000)
    #termination_strategy = TimeSpentLimit(time_seconds_limit=600)
    termination_strategy = ScoreNoImprovement(time_seconds_limit=30)
    #termination_strategy = ScoreLimit(score_to_compare=[0])
    """agent = TabuSearch(neighbours_count=128, tabu_entity_rate=0.05, 
                    mutation_rate_multiplier=None, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                    migration_frequency=10, compare_to_global_frequency=0, termination_strategy=termination_strategy)"""
    agent = LateAcceptance(late_acceptance_size=128, tabu_entity_rate=0.05, 
                        mutation_rate_multiplier=None, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                        migration_frequency=10000, compare_to_global_frequency=0, termination_strategy=termination_strategy)
    """agent = SimulatedAnnealing(initial_temperature=[1.0, 1.0], cooling_rate=0.9999, tabu_entity_rate=0.05, 
                            mutation_rate_multiplier=None, move_probas=None, 
                            migration_frequency=1000, compare_to_global_frequency=0, termination_strategy=termination_strategy)"""
    
    solver = SolverOOP(domain_builder, cotwin_builder, agent, 
                    ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                    n_jobs=10, score_precision=[0, 0])
    solution = solver.solve()
    
    domain = domain_builder.build_from_solution(solution)
    domain.print_schedule()

    print( "done" )