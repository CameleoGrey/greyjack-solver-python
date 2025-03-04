from pathlib import Path
import os
import sys

# To launch normally from console without setup.py greyjack (just for developing)
# Inside console run from from project dir: >python ./{path_to_example_script.py}
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from copy import deepcopy

from examples.object_oriented.nqueens.persistence.DomainGenerator import DomainGenerator
from examples.object_oriented.nqueens.persistence.CotwinBuilder import CotwinBuilder
from examples.object_oriented.nqueens.persistence.DomainUpdater import DomainUpdater
#from greyjack.score_calculation.scores.SimpleScore import SimpleScore
#from greyjack.agents.termination_strategies import *
#from greyjack.agents import *
#from greyjack.Solver import Solver


if __name__ == "__main__":
    # build domain model
    chess_field = DomainGenerator.generate_domain( 256, random_seed=45 )
    #print( "Chess field before solving: " )
    #print( chess_field )

    # translate human-oriented domain model to solver-oriented model (cotwin)
    nqueens_cotwin = CotwinBuilder().build_cotwin( chess_field )

    #termination_strategy = StepsLimit(step_count_limit=5000)
    """termination_strategy = TimeSpentLimit(time_seconds_limit=60)
    #termination_strategy = ScoreNoImprovement(time_seconds_limit=15)
    #termination_strategy = ScoreLimit(score_to_compare=SimpleScore(0))
    agent = TabuSearch(neighbours_count=20, tabu_entity_rate=0.0, 
                       mutation_rate_multiplier=None, move_probas=None, 
                       migration_frequency=1, termination_strategy=termination_strategy)


    agents_list = [deepcopy(agent) for i in range(10)]
    solver = Solver(agents=agents_list, score_precision=[0], logging_level="info", 
                    parallelization_backend="processing", #processing, threading
                    random_seed=45)
    solution = solver.solve( model=nqueens_cotwin )
    print( "Cotwin solution looks that: " )
    print( solution )

    # updating human-oriented domain model by solved cotwin model
    chess_field = DomainUpdater.update_domain( chess_field, solution )
    print( "Chess field after solving: " )
    print( chess_field )"""

    print( "done" )