import random
from collections import defaultdict
import numpy as np

# mostly rewrited by LLM (Rust->Python) for tests purpose only. Will be replaced by normally wrapped Rust version
class VariablesManager:
    def __init__(self, variables_vec):
        self.variables_vec = variables_vec
        self.variables_count = len(variables_vec)
        self.variable_ids = []
        self.lower_bounds = []
        self.upper_bounds = []
        self.discrete_ids = []

        for i in range(self.variables_count):
            self.variable_ids.append(i)
            current_variable = variables_vec[i]
            self.lower_bounds.append(current_variable.lower_bound)
            self.upper_bounds.append(current_variable.upper_bound)
            if current_variable.is_int:
                self.discrete_ids.append(i)

        self.semantic_groups_map = self.build_semantic_groups_dict(variables_vec)
        self.semantic_group_keys = list(self.semantic_groups_map.keys())
        self.n_semantic_groups = len(self.semantic_group_keys)
        self.discrete_ids = self.discrete_ids if self.discrete_ids else None

    @staticmethod
    def build_semantic_groups_dict(variables_vec):
        semantic_groups_dict = defaultdict(list)
        for i, variable in enumerate(variables_vec):
            variable_semantic_groups = variable.semantic_groups
            is_frozen_variable = variable.frozen

            for group_name in variable_semantic_groups:
                if group_name not in semantic_groups_dict:
                    semantic_groups_dict[group_name] = []
                if is_frozen_variable:
                    continue
                semantic_groups_dict[group_name].append(i)
        return semantic_groups_dict

    def get_random_semantic_group_ids(self):
        random_group_id = random.randint(0, self.n_semantic_groups - 1)
        group_name = self.semantic_group_keys[random_group_id]
        group_ids = self.semantic_groups_map[group_name]
        return group_ids, group_name

    def get_column_random_value(self, column_id):
        return random.uniform(self.lower_bounds[column_id], self.upper_bounds[column_id])

    def sample_variables(self):
        values_array = np.zeros(self.variables_count)
        for i in range(self.variables_count):
            variable = self.variables_vec[i]
            generated_value = variable.get_initial_value()
            values_array[i] = generated_value
        return values_array

    def get_variables_names_vec(self):
        return [variable.name for variable in self.variables_vec]

    def fix_variables(self, values_array, ids_to_fix=None):
        range_ids = ids_to_fix if ids_to_fix is not None else list(range(self.variables_count))
        for i in range_ids:
            values_array[i] = self.variables_vec[i].fix(values_array[i])

    def fix_deltas(self, deltas, ids_to_fix=None):
        range_ids = ids_to_fix if ids_to_fix is not None else list(range(self.variables_count))
        for delta_id, var_id in enumerate(range_ids):
            deltas[delta_id] = self.variables_vec[var_id].fix(deltas[delta_id])