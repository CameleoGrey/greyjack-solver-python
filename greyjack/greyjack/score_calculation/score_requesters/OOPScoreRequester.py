
from typing import Dict, List, Tuple, Any
import polars as pl
import numpy as np
from collections import defaultdict
from greyjack.score_calculation.score_requesters.VariablesManager import VariablesManager
from greyjack.greyjack import GJPlanningVariablePy, VariablesManagerPy
from greyjack.variables import *

# mostly rewrited by LLM from Rust to Python 
class OOPScoreRequester:
    def __init__(self, cotwin):
        self.cotwin = cotwin

        self.available_planning_variable_types = {GJFloat, GJInteger, GJBinary}
        variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map = self.build_variables_info()
        self.variables_manager = VariablesManagerPy(variables_vec)

        self.var_name_to_df_col_names = {}
        self.var_name_to_vec_id_map = var_name_to_vec_id_map
        self.vec_id_to_var_name_map = vec_id_to_var_name_map
        self.df_column_to_var_ids_map = {}
        self.var_id_to_df_column_index_map = []
        self.var_id_to_df_name = []
        self.var_id_to_col_name = []

        self.cached_sample_id_vectors = {}
        self.cached_sample_size = 999_999_999

        self.planning_entities_column_map = self.build_column_map(self.cotwin.planning_entities)
        self.problem_facts_column_map = self.build_column_map(self.cotwin.problem_facts)
        self.planning_entity_dfs = self.build_group_dfs(self.cotwin.planning_entities, self.planning_entities_column_map, True)
        self.problem_fact_dfs = self.build_group_dfs(self.cotwin.problem_facts, self.problem_facts_column_map, False)
        self.raw_dfs = self.planning_entity_dfs.copy()

    # mostly from prototype
    def build_variables_info(self):
        variables_vec = []
        var_name_to_vec_id_map = {}
        vec_id_to_var_name_map = {}

        i = 0
        for planning_entities_group_name in self.cotwin.planning_entities:
            current_planning_entities_group = self.cotwin.planning_entities[planning_entities_group_name]
            for entity in current_planning_entities_group:
                entity_attributes_dict = entity.__dict__
                for attribute_name in entity_attributes_dict:
                    attribute_value = entity_attributes_dict[attribute_name]
                    if type(attribute_value) not in self.available_planning_variable_types:
                        continue
                    variable = attribute_value
                    full_variable_name = planning_entities_group_name + ": " + str(i) + "-->" + attribute_name
                    variable.planning_variable.name = full_variable_name
                    var_name_to_vec_id_map[full_variable_name] = i
                    vec_id_to_var_name_map[i] = full_variable_name
                    variables_vec.append(variable.planning_variable)
                    i += 1

        return variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map

    # original from prototype
    def build_column_map(self, entity_groups):
        
        # Python dict saves order, that's why when I was using HashMap in Rust
        # there was bug, until I added cotwin object conversion .to_vec()
        column_dict = {}
        for group_name in entity_groups:
            column_dict[group_name] = []
            entity_objects = entity_groups[group_name]
            sample_object = entity_objects[0]
            object_attributes = sample_object.__dict__
            for attribute_name in object_attributes:
                column_dict[group_name].append( attribute_name )

        return column_dict

    # original from prototype
    def build_group_dfs(self, entity_groups, column_dict, is_planning):

        df_dict = {}

        for df_name in column_dict:
            column_names = column_dict[df_name]
            df_data = []

            entity_group = entity_groups[df_name]
            entities_count = len(entity_group)
            for entity_object in entity_group:
                row_data = []
                object_attributes = entity_object.__dict__
                for column_name in column_names:
                    attribute_value = object_attributes[column_name]
                    if type(attribute_value) in self.available_planning_variable_types:
                        attribute_value = None
                    row_data.append( attribute_value )
                if is_planning:
                    row_data = [0] + row_data
                df_data.append( row_data )
            if is_planning:
                column_names = ["sample_id"] + column_names
            df = pl.DataFrame( data=df_data, schema=column_names, orient="row" )

            df_dict[df_name] = df


        return df_dict

    # rewrited from Rust to Python by LLM
    """def build_column_map(self, entity_groups):
        column_map = {}
        for group_name, entity_objects in entity_groups.items():
            group_columns = []
            sample_object = entity_objects[0]
            entity_field_names = sample_object.to_vec()
            for name, _ in entity_field_names:
                group_columns.append(name)
            column_map[group_name] = group_columns
        return column_map

    def build_group_dfs(self, entity_groups, column_map, is_planning):
        df_map = {}
        for df_name, column_names in column_map.items():
            entity_group = entity_groups[df_name]
            entities_count = len(entity_group)

            entity_fields_data = {column_name: [] for column_name in column_names}
            for entity_object in entity_group:
                entity_vec_representation = entity_object.to_vec()
                for name, value in entity_vec_representation:
                    if isinstance(value, GJF) or isinstance(value, GJI):
                        field_polars_value = None
                    elif isinstance(value, PAV):
                        field_polars_value = value
                    entity_fields_data[name].append(field_polars_value)

            columns = {column_name: entity_fields_data[column_name] for column_name in column_names}
            df = pl.DataFrame(columns)

            if is_planning:
                df["sample_id"] = [0] * entities_count

            df_map[df_name] = df
        return df_map"""

    def update_dfs_for_scoring(self, group_data_map, samples_count, add_row_index):

        """
        for df_name in group_data_dict:
            current_df = self.dfs_for_scoring[df_name].__copy__()
            rows_count = len(samples_list) * len(current_df)
            if len(current_df) != rows_count:
                current_df = pl.concat([current_df for i in range(len(samples_list))])

            updated_columns = []
            for column_name in group_data_dict[df_name]:
                current_df.drop_in_place(column_name)
                updated_column = pl.Series(name=column_name, values=group_data_dict[df_name][column_name])
                updated_columns.append( updated_column )
            current_df = current_df.with_columns(updated_columns)
            current_df = current_df.rechunk()

            self.planning_entity_dfs[df_name] = current_df
        """

        for df_name, data in group_data_map.items():
            current_df = self.planning_entity_dfs[df_name].clone()
            needful_rows_count = samples_count * len(self.raw_dfs[df_name])
            if len(current_df) != needful_rows_count:
                new_df_parts = [self.raw_dfs[df_name].clone() for _ in range(samples_count)]
                current_df = pl.concat(new_df_parts)

            updated_columns = []
            for column_name in group_data_map[df_name]:
                current_df.drop_in_place(column_name)
                updated_column = pl.Series(name=column_name, values=group_data_map[df_name][column_name])
                updated_columns.append( updated_column )
            current_df = current_df.with_columns(updated_columns)
            current_df = current_df.rechunk()

            if add_row_index:
                current_df = current_df.with_row_index("candidate_df_row_id", offset=None)

            self.planning_entity_dfs[df_name] = current_df

    def get_df_column_name(self, variable_name):
        df_name_parts = variable_name.split(": ")
        df_name = df_name_parts[0]

        column_name_parts = variable_name.split("-->")
        column_name = column_name_parts[-1]

        return df_name, column_name

    def build_var_mappings(self):
        variable_names = self.variables_manager.get_variables_names_vec()
        df_column_var_ids = {}

        for i, var_name in enumerate(variable_names):
            df_name, column_name = self.get_df_column_name(var_name)

            self.var_id_to_df_name.append(df_name)
            self.var_id_to_col_name.append(column_name)

            if (df_name, column_name) not in df_column_var_ids:
                df_column_var_ids[(df_name, column_name)] = []
            
            df_column_var_ids[(df_name, column_name)].append(i)

        return df_column_var_ids

    def build_group_data_map(self, samples_vec, include_sample_id_column):
        if len(self.df_column_to_var_ids_map) == 0:
            self.df_column_to_var_ids_map = self.build_var_mappings()

        group_data_map = {}
        n_variables = self.variables_manager.variables_count  # Define `variables_count` according to needs

        for df_name, col_name in self.df_column_to_var_ids_map.keys():
            if df_name not in group_data_map:
                group_data_map[df_name] = {}
            group_data_map[df_name][col_name] = []

        for df_col_name, var_ids in self.df_column_to_var_ids_map.items():
            for sample_vec in samples_vec:
                current_sample_column = [sample_vec[i] for i in var_ids]
                group_data_map[df_col_name[0]][df_col_name[1]].extend(current_sample_column)

        if include_sample_id_column:
            if len(samples_vec) != self.cached_sample_size:
                df_names = list(group_data_map.keys())
                for df_name in df_names:
                    group_keys = list(group_data_map[df_name].keys())
                    first_group_key = group_keys[0]
                    updated_df_column_len = len(group_data_map[df_name][first_group_key])
                    samples_count = len(samples_vec)
                    true_df_len = updated_df_column_len // samples_count
                    correct_sample_ids = []

                    for i in range(samples_count):
                        correct_sample_ids.extend([i for _ in range(true_df_len)])

                    self.cached_sample_size = len(samples_vec)
                    self.cached_sample_id_vectors[df_name] = [vec_value for vec_value in correct_sample_ids]

                    group_data_map[df_name]["sample_id"] = correct_sample_ids
            else:
                for df_name in self.cached_sample_id_vectors.keys():
                    group_data_map[df_name]["sample_id"] = [x for x in self.cached_sample_id_vectors[df_name]]

        return group_data_map

    def request_score_plain(self, samples):
        discrete_ids = self.variables_manager.discrete_ids
        if discrete_ids is not None:
            for sample in samples:
                for discrete_id in discrete_ids:
                    sample[discrete_id] = int(sample[discrete_id])
        candidates = samples
        group_data_map = self.build_group_data_map(candidates, True)
        samples_count = len(candidates)
        self.update_dfs_for_scoring(group_data_map, samples_count, False)
        score_batch = self.cotwin.get_score(self.planning_entity_dfs, self.problem_fact_dfs)
        return score_batch

    def build_var_id_to_df_column_index_map(self):
        var_id_to_df_column_index_map = []
        increment_row_id_map = defaultdict(int)
        for var_id, (df_name, col_name) in enumerate(zip(self.var_id_to_df_name, self.var_id_to_col_name)):
            current_row_id = increment_row_id_map[(df_name, col_name)]
            var_id_to_df_column_index_map.append((df_name, col_name, current_row_id))
            increment_row_id_map[(df_name, col_name)] += 1
        return var_id_to_df_column_index_map

    def build_delta_dfs(self, group_data_map, inverted_deltas):
        if not self.var_id_to_df_column_index_map:
            self.var_id_to_df_column_index_map = self.build_var_id_to_df_column_index_map()

        delta_data_map = defaultdict(lambda: defaultdict(list))
        for sample_id, current_sample_deltas in enumerate(inverted_deltas):
            for var_id, new_value in current_sample_deltas:
                df_name, var_col_name, row_id = self.var_id_to_df_column_index_map[var_id]
                delta_data_map[df_name]["sample_id"].append(sample_id)
                delta_data_map[df_name]["candidate_df_row_id"].append(row_id)

                for column_name, column_values in group_data_map[df_name].items():
                    if column_name == var_col_name:
                        delta_data_map[df_name][column_name].append(new_value)
                    else:
                        delta_data_map[df_name][column_name].append(column_values[row_id])

        delta_dfs = {}
        for df_name, data in delta_data_map.items():
            df = pl.DataFrame(data)
            df = df.sort_values(by=["sample_id", "candidate_df_row_id"])
            delta_dfs[df_name] = df
        return delta_dfs

    def request_score_incremental(self, sample, deltas):

        discrete_ids = self.variables_manager.discrete_ids
        if discrete_ids is not None:
            for discrete_id in discrete_ids:
                sample[discrete_id] = int(sample[discrete_id])
        candidate = sample

        group_data_map = self.build_group_data_map([candidate], False)
        self.update_dfs_for_scoring(group_data_map, 1, True)
        inverted_deltas = self.variables_manager.inverse_transform_deltas(deltas)
        delta_dfs = self.build_delta_dfs(group_data_map, inverted_deltas)
        score_batch = self.cotwin.get_score(self.planning_entity_dfs, self.problem_fact_dfs, delta_dfs)
        return score_batch