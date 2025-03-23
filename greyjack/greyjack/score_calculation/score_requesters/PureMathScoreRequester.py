
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.greyjack import VariablesManagerPy
from greyjack.pure_math.MathModel import MathModel
from greyjack.pure_math.variables.FloatVar import FloatVar
from greyjack.pure_math.variables.IntegerVar import IntegerVar
from greyjack.pure_math.variables.BinaryVar import BinaryVar
from greyjack.variables.GJFloat import GJFloat
from greyjack.variables.GJInteger import GJInteger
from greyjack.variables.GJBinary import GJBinary
import numpy as np

class PureMathScoreRequester():

    def __init__(self, math_model: MathModel):

        self.math_model = math_model

        for var_name in self.math_model.variables.keys():
            proxy_variable = self.math_model.variables[var_name]
            if isinstance(proxy_variable, BinaryVar):
                planning_variable = GJBinary(proxy_variable.frozen, proxy_variable.initial_value, proxy_variable.semantic_groups).planning_variable
            elif isinstance(proxy_variable, IntegerVar):
                planning_variable = GJInteger(proxy_variable.lower_bound, proxy_variable.upper_bound, proxy_variable.frozen, 
                                              proxy_variable.initial_value, proxy_variable.semantic_groups).planning_variable
            elif isinstance(proxy_variable, FloatVar):
                planning_variable = GJFloat(proxy_variable.lower_bound, proxy_variable.upper_bound, proxy_variable.frozen, 
                                            proxy_variable.initial_value, proxy_variable.semantic_groups).planning_variable
            else:
                raise Exception("Variables of MathModel must be of types: BinaryVar, IntegerVar, FloatVar. Current error variable name | type: {} | {}".format(var_name, type(proxy_variable)))
            planning_variable.name = var_name
            self.math_model.variables[var_name] = planning_variable

        self.available_planning_variable_types = {GJFloat, GJInteger, GJBinary}
        self.var_name_to_arr_id_map = {}
        self.arr_id_to_var_name_map = {}
        for arr_id, var_name in enumerate(math_model.variables.keys()):
            self.var_name_to_arr_id_map[var_name] = arr_id
            self.arr_id_to_var_name_map[arr_id] = var_name

        variables_list = []
        for var_name in self.var_name_to_arr_id_map.keys():
            current_variable = math_model.variables[var_name]
            variables_list.append( current_variable )
        self.variables_manager = VariablesManagerPy(variables_list)
        self.n_variables = len(variables_list)
        self.discrete_ids = self.variables_manager.discrete_ids
        self.discrete_var_names = set()
        if self.discrete_ids is not None:
            for discrete_id in self.discrete_ids:
                self.discrete_var_names.add(self.arr_id_to_var_name_map[discrete_id])

    def request_score_plain(self, samples):

        score_batch = []

        for sample in samples:

            if self.discrete_ids is not None:
                for i in self.discrete_ids:
                    sample[i] = int(np.rint(sample[i]))

            for i in range(self.n_variables):
                self.math_model.variables[self.arr_id_to_var_name_map[i]] = sample[i]

            hard_score_value = self.math_model.get_sum_hard_score(absolute=True)
            soft_score_value = self.math_model.get_sum_soft_score(is_fitting=True)
            score = HardSoftScore(hard_score_value, soft_score_value)

            score_batch.append(score)

        return score_batch
    
    def request_score_incremental(self, sample, deltas):

        score_batch = []

        if self.discrete_ids is not None:
            for i in self.discrete_ids:
                sample[i] = int(np.rint(sample[i]))
        for i in range(self.n_variables):
            self.math_model.variables[self.arr_id_to_var_name_map[i]] = sample[i]
        
        if self.math_model.variable_to_constraint_index is None:
            self.math_model.variable_to_contstraint_index = self.math_model._build_variable_to_constraint_index(self.variables_manager, self.var_name_to_arr_id_map, self.discrete_var_names)

        hard_score_values_before = self.math_model.get_individual_hard_scores(absolute=True)
        sum_hard_score_before = sum(hard_score_values_before.values())
        #soft_score_value_before = self.math_model.get_sum_soft_score(is_fitting=True)

        score_batch = []
        for sample_deltas in deltas:
            var_names = []
            values_before = []
            touched_constraints = []
            for (i, new_value) in sample_deltas:
                var_name = self.arr_id_to_var_name_map[i]
                var_names.append(var_name)
                values_before.append( self.math_model.variables[var_name] )
                self.math_model.variables[var_name] = new_value
                touched_constraints.append(self.math_model.variable_to_contstraint_index[var_name])
            touched_constraints = set.union(*touched_constraints)
            
            sample_hard_score = sum_hard_score_before
            for constraint_name in touched_constraints:
                sample_hard_score -= hard_score_values_before[constraint_name]
                sample_hard_score += abs(self.math_model.constraints[constraint_name].get_hard_score(self.math_model.variables, self.math_model.utility))
            sample_soft_score = self.math_model.get_sum_soft_score(is_fitting=True)

            score_batch.append(HardSoftScore(sample_hard_score, sample_soft_score))

            for i in range(len(var_names)):
                self.math_model.variables[var_names[i]] = values_before[i]
        
        return score_batch
            


