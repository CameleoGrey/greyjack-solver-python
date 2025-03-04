
import numpy as np
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore


class Individual:

    def __init__(self, variable_values=None, score=None):
        self.variable_values = variable_values
        self.score = score

    def copy(self):
        individual = Individual(self.variable_values.copy(), self.scopy())
        return individual

    def __lt__(self, other):
        return self.score < other.score
    
    def as_list(self):
        return [self.variable_values.tolist(), self.score.as_list()]
    
    @staticmethod
    def from_list(list_individual):
        # TODO: generalize to more level scores
        score_len = len(list_individual[1])
        if score_len == 1:
            score_type = SimpleScore
        elif score_len == 2:
            score_type = HardSoftScore
        else:
            raise ("Can't define score type while inverse converting of list of individuals-lists")
        
        variable_array = np.array( list_individual[0], dtype=np.float64 )
        score = score_type( *list_individual[1] )
        individual = Individual( variable_array, score )

        return individual

    @staticmethod
    def convert_individuals_to_lists(individuals_list):

        list_of_lists = []
        for individual in individuals_list:
            list_of_lists.append( individual.as_list() )
        
        return list_of_lists
    
    @staticmethod
    def convert_lists_to_individuals(list_of_lists):
        
        # TODO: generalize to more level scores
        score_len = len(list_of_lists[0][1])
        if score_len == 1:
            score_type = SimpleScore
        elif score_len == 2:
            score_type = HardSoftScore
        else:
            raise ("Can't define score type while inverse converting of list of individuals-lists")

        individuals_list = []
        for list_individual in list_of_lists:
            variable_array = np.array( list_individual[0], dtype=np.float64 )
            score = score_type( *list_individual[1] )
            individual = Individual( variable_array, score )
            individuals_list.append( individual )
        
        return individuals_list


