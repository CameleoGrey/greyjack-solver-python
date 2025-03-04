
from typing import Dict, List, Tuple, Any
import polars as pl
import numpy as np
from collections import defaultdict

# rewrited by LLM from Rust to Python
# TODO: fix errors, refactor
# TODO: LLM changed polars to pandas, need to return to polars functions
# TODO: build 1 time all needful mappings, build Rust implementation (convert mappings to Rust types), send to cotwin.get_score() candidates built by Rust back 
class OOPScoreRequester:
    def __init__(self, cotwin):
        self.cotwin = cotwin
        self.variables_manager = VariablesManager()

        self.var_name_to_df_col_names = {}
        self.var_name_to_vec_id_map = {}
        self.vec_id_to_var_name_map = {}
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

    def build_variables_info(self):
        variables_vec = []
        var_name_to_vec_id_map = {}
        vec_id_to_var_name_map = {}

        i = 0
        for planning_entities_group_name, current_planning_entities_group in self.cotwin.planning_entities.items():
            for entity in current_planning_entities_group:
                entity_attributes_map = entity.to_vec()

                for attribute_name, attribute_value in entity_attributes_map.items():
                    full_variable_name = f"{planning_entities_group_name}: {i}-->{attribute_name}"
                    if isinstance(attribute_value, GJF):
                        attribute_value.set_name(full_variable_name)
                        variable = PlanningVariablesVariants.GJF(attribute_value)
                    elif isinstance(attribute_value, GJI):
                        attribute_value.set_name(full_variable_name)
                        variable = PlanningVariablesVariants.GJI(attribute_value)
                    elif isinstance(attribute_value, PAV):
                        continue

                    var_name_to_vec_id_map[full_variable_name] = i
                    vec_id_to_var_name_map[i] = full_variable_name
                    variables_vec.append(variable)
                    i += 1

        return variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map
    

    # original from prototype
    def _build_column_dict(self, entity_groups):
        
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

    def _build_group_dfs(self, entity_groups, column_dict):

        df_dict = {}

        for df_name in column_dict:
            column_names = column_dict[df_name]
            df_data = []

            entity_group = entity_groups[df_name]
            for entity_object in entity_group:
                row_data = []
                object_attributes = entity_object.__dict__
                for column_name in column_names:
                    attribute_value = object_attributes[column_name]
                    if type(attribute_value) in self.available_planning_variable_types:
                        attribute_value = None
                    row_data.append( attribute_value )
                row_data = [0] + row_data
                df_data.append( row_data )
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
        for df_name, data in group_data_map.items():
            current_df = self.planning_entity_dfs[df_name].copy()
            needful_rows_count = samples_count * len(self.raw_dfs[df_name])
            if len(current_df) != needful_rows_count:
                new_df_parts = [self.raw_dfs[df_name].copy() for _ in range(samples_count)]
                current_df = pl.concat(new_df_parts, ignore_index=True)

            for column_name, updated_column_data in data.items():
                current_df.drop(column_name, axis=1, inplace=True)
                current_df[column_name] = updated_column_data

            if add_row_index:
                current_df.reset_index(drop=True, inplace=True)

            self.planning_entity_dfs[df_name] = current_df

    def get_df_column_name(self, variable_name):
        df_name = variable_name.split(": ")[0]
        column_name = variable_name.split("-->")[-1]
        return df_name, column_name

    def build_var_mappings(self):
        variable_names = self.variables_manager.get_variables_names_vec()
        df_column_var_ids = defaultdict(list)
        for i, var_name in enumerate(variable_names):
            df_name, column_name = self.get_df_column_name(var_name)
            self.var_id_to_df_name.append(df_name)
            self.var_id_to_col_name.append(column_name)
            df_column_var_ids[(df_name, column_name)].append(i)
        return df_column_var_ids

    def build_group_data_map(self, samples_vec, include_sample_id_column):
        if not self.df_column_to_var_ids_map:
            self.df_column_to_var_ids_map = self.build_var_mappings()

        group_data_map = defaultdict(lambda: defaultdict(list))
        for (df_name, col_name), var_ids in self.df_column_to_var_ids_map.items():
            for sample_vec in samples_vec:
                current_sample_column = [sample_vec[i] for i in var_ids]
                group_data_map[df_name][col_name].extend(current_sample_column)

        if include_sample_id_column:
            if len(samples_vec) != self.cached_sample_size:
                for df_name in group_data_map.keys():
                    first_group_key = next(iter(group_data_map[df_name].keys()))
                    updated_df_column_len = len(group_data_map[df_name][first_group_key])
                    samples_count = len(samples_vec)
                    true_df_len = updated_df_column_len // samples_count
                    correct_sample_ids = [i for i in range(samples_count) for _ in range(true_df_len)]
                    self.cached_sample_size = len(samples_vec)
                    self.cached_sample_id_vectors[df_name] = correct_sample_ids
                    group_data_map[df_name]["sample_id"] = correct_sample_ids
            else:
                for df_name, sample_ids in self.cached_sample_id_vectors.items():
                    group_data_map[df_name]["sample_id"] = sample_ids

        return group_data_map

    def request_score_plain(self, samples):
        candidates = [self.variables_manager.inverse_transform_variables(sample) for sample in samples]
        group_data_map = self.build_group_data_map(candidates, True)
        samples_count = len(candidates)
        self.update_dfs_for_scoring(group_data_map, samples_count, False)
        score_batch = self.cotwin.get_score(self.planning_entity_dfs, self.problem_fact_dfs, None)
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
        candidate = self.variables_manager.inverse_transform_variables(sample)
        group_data_map = self.build_group_data_map([candidate], False)
        self.update_dfs_for_scoring(group_data_map, 1, True)
        inverted_deltas = self.variables_manager.inverse_transform_deltas(deltas)
        delta_dfs = self.build_delta_dfs(group_data_map, inverted_deltas)
        score_batch = self.cotwin.get_score(self.planning_entity_dfs, self.problem_fact_dfs, delta_dfs)
        return score_batch