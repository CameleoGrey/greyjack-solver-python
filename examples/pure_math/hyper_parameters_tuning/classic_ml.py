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


from copy import deepcopy

from greyjack.SolverPureMath import SolverPureMath
from greyjack.agents import *
from greyjack.agents.termination_strategies import *
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents.base.LoggingLevel import LoggingLevel

from greyjack.pure_math.MathModel import MathModel
from greyjack.pure_math.Objective import Objective
from greyjack.pure_math.Constraint import Constraint
from greyjack.pure_math.variables.FloatVar import FloatVar
from greyjack.pure_math.variables.IntegerVar import IntegerVar
from greyjack.pure_math.variables.BinaryVar import BinaryVar

import sklearn.datasets
import sklearn.linear_model
from sklearn.model_selection import train_test_split
from sklearn.tree import ExtraTreeClassifier

from copy import deepcopy


def build_math_model():
    
    m = MathModel()
    
    m.variables["max_depth"] = IntegerVar(2, 8)
    m.variables["ccp_alpha"] = FloatVar(1e-5, 1e-1)
    m.variables["criterion"] = IntegerVar(0, 2)
    m.utility["criterion_name_map"] = {0: "gini", 1: "entropy", 2: "log_loss"}

    dataset = sklearn.datasets.load_digits()
    train_x, valid_x, train_y, valid_y = train_test_split( dataset.data, dataset.target, test_size=0.25, random_state=0)
    m.utility["train_x"] = train_x
    m.utility["train_y"] = train_y
    m.utility["valid_x"] = valid_x
    m.utility["valid_y"] = valid_y
    m.utility["ExtraTreeClassifier"] = ExtraTreeClassifier

    def get_score(v, u):
        criterion = u["criterion_name_map"][v["criterion"]]
        classifier = u["ExtraTreeClassifier"](max_depth=v["max_depth"], ccp_alpha=v["ccp_alpha"], criterion=criterion, random_state=45)
        classifier.fit( u["train_x"], u["train_y"] )
        score = 1.0 - classifier.score( u["valid_x"], u["valid_y"] )
        return score
    m.objectives["score"] = Objective("minimize", lambda v, u: get_score(v, u))

    return m

if __name__ == "__main__":

    """
    Example just shows the common structure for case of optimization hyper-parameters.
    """

    math_model = build_math_model()

    termination_strategy = ScoreNoImprovement(time_seconds_limit=5)
    #termination_strategy = StepsLimit(step_count_limit=100)
    """agent = GeneticAlgorithm(population_size=128, crossover_probability=0.8, p_best_rate=0.5,
                             tabu_entity_rate=0.0, mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                             migration_rate=0.00001, migration_frequency=1, termination_strategy=termination_strategy)"""
    agent = TabuSearch(neighbours_count=20, tabu_entity_rate=0.2, 
                       mutation_rate_multiplier=1.0, move_probas=[0.5, 0.5, 0.0, 0.0, 0.0, 0.0], 
                       compare_to_global_frequency=1, termination_strategy=termination_strategy)
    
    solver = SolverPureMath(math_model, agent,
                            ParallelizationBackend.Multiprocessing, LoggingLevel.FreshOnly,
                            n_jobs=10, score_precision=[10, 10])
    solution = solver.solve()
    print( solution )

    math_model.explain_solution( solution )

    print( "done" )