# greyjack/score_calculation/score_requesters/OOPScoreRequester.py

import polars as pl
from greyjack.greyjack import VariablesManagerPy, CandidateDfsBuilderPy
from greyjack.variables.GJFloat import GJFloat
from greyjack.variables.GJInteger import GJInteger
from greyjack.variables.GJBinary import GJBinary
from greyjack.score_calculation.score_calculators.GreynetScoreCalculator import GreynetScoreCalculator
import traceback

class OOPScoreRequester:
    def __init__(self, cotwin):
        self.cotwin = cotwin
        variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map = self.build_variables_info(self.cotwin)
        self.variables_manager = VariablesManagerPy(variables_vec)
        self.vec_id_to_var_name_map = vec_id_to_var_name_map

        self.is_greynet = isinstance(self.cotwin.score_calculator, GreynetScoreCalculator)

        if self.is_greynet:
            self._init_greynet()
        else:
            self._init_plain(variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map)

    def _init_greynet(self):
        """Initializes the requester and calculator for Greynet mode."""
        calculator = self.cotwin.score_calculator

        initialized_planning_entities = {}
        for group_name in self.cotwin.planning_entities:
            current_initialized_entities = self.build_initialized_entities(self.cotwin.planning_entities, group_name)
            initialized_planning_entities[group_name] = current_initialized_entities

        # Build the crucial mapping from solver's variable index to the domain object
        var_idx_to_entity_map = {}
        i = 0
        for group_name in self.cotwin.planning_entities:
            for native_entity, initialized_entity in zip(self.cotwin.planning_entities[group_name], initialized_planning_entities[group_name]):
                for attr_name, attr_value in native_entity.__dict__.items():
                    if type(attr_value) in {GJFloat, GJInteger, GJBinary}:
                        var_idx_to_entity_map[i] = (initialized_entity, attr_name)
                        i += 1
        calculator.var_idx_to_entity_map = var_idx_to_entity_map

        
        calculator.initial_load(initialized_planning_entities, self.cotwin.problem_facts)
    
    def build_initialized_entities(self, planning_entities, group_name):

        current_planning_entities_group = planning_entities[group_name]
        initialized_entities = []

        for entity in current_planning_entities_group:
            new_entity = self.build_initialized_entity(entity)
            initialized_entities.append(new_entity)
        
        return initialized_entities
    
    def build_initialized_entity(self, entity):
        
        entity_attributes_dict = entity.__dict__

        new_entity_kwargs = {}
        for attribute_name in entity_attributes_dict:
            attribute_value = entity_attributes_dict[attribute_name]

            if type(attribute_value) in {GJFloat, GJInteger, GJBinary}:
                value = attribute_value.planning_variable.initial_value
                if value is None:
                    raise ValueError("All planning variables must have initial value for scoring by greynet")
            else:
                value = attribute_value
            
            new_entity_kwargs[attribute_name] = value
        del new_entity_kwargs["greynet_fact_id"]
            
        new_entity = type(entity)(**new_entity_kwargs)
        new_entity.greynet_fact_id = entity.greynet_fact_id

        return new_entity

    def _init_plain(self, variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map):
        """Initializes the requester for the standard DataFrame-based calculation."""
        planning_entities_column_map, entity_is_int_map = self.build_column_map(self.cotwin.planning_entities)
        problem_facts_column_map, _ = self.build_column_map(self.cotwin.problem_facts)
        planning_entity_dfs = self.build_group_dfs(self.cotwin.planning_entities, planning_entities_column_map, True)
        problem_fact_dfs = self.build_group_dfs(self.cotwin.problem_facts, problem_facts_column_map, False)

        self.candidate_dfs_builder = CandidateDfsBuilderPy(
            variables_vec,
            var_name_to_vec_id_map, 
            vec_id_to_var_name_map,
            planning_entities_column_map,
            problem_facts_column_map,
            planning_entity_dfs,
            problem_fact_dfs,
            entity_is_int_map
        )
        
    def request_score_plain(self, samples):
        if self.is_greynet:
            return [self.cotwin.score_calculator._full_sync_and_get_score(s) for s in samples]
        else:
            planning_entity_dfs, problem_fact_dfs = self.candidate_dfs_builder.get_plain_candidate_dfs(samples)
            return self.cotwin.get_score_plain(planning_entity_dfs, problem_fact_dfs)

    def request_score_incremental(self, sample, deltas):
        if self.is_greynet:
            return self.cotwin.score_calculator._apply_and_get_score_for_batch(deltas)
        else:
            planning_entity_dfs, problem_fact_dfs, delta_dfs_for_rust = self.candidate_dfs_builder.get_incremental_candidate_dfs(sample, deltas)
            return self.cotwin.get_score_incremental(planning_entity_dfs, problem_fact_dfs, delta_dfs_for_rust)

    def build_variables_info(self, cotwin):
        variables_vec = []
        var_name_to_vec_id_map = {}
        vec_id_to_var_name_map = {}
        i = 0
        for planning_entities_group_name in cotwin.planning_entities:
            current_planning_entities_group = cotwin.planning_entities[planning_entities_group_name]
            for entity in current_planning_entities_group:
                entity_attributes_dict = entity.__dict__
                for attribute_name in entity_attributes_dict:
                    attribute_value = entity_attributes_dict[attribute_name]
                    if type(attribute_value) in {GJFloat, GJInteger, GJBinary}:
                        variable = attribute_value
                        full_variable_name = f"{planning_entities_group_name}: {i}-->{attribute_name}"
                        variable.planning_variable.name = full_variable_name
                        var_name_to_vec_id_map[full_variable_name] = i
                        vec_id_to_var_name_map[i] = full_variable_name
                        variables_vec.append(variable.planning_variable)
                        i += 1
        return variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map

    def build_column_map(self, entity_groups):
        column_dict = {}
        entity_is_int_map = {}
        for group_name in entity_groups:
            column_dict[group_name] = []
            entity_objects = entity_groups[group_name]
            if not entity_objects: continue
            sample_object = entity_objects[0]
            object_attributes = sample_object.__dict__
            for attribute_name, attribute_value in object_attributes.items():
                column_dict[group_name].append(attribute_name)
                if isinstance(attribute_value, GJFloat):
                    entity_is_int_map[attribute_name] = False
                else:
                    entity_is_int_map[attribute_name] = True
        return column_dict, entity_is_int_map
    
    def build_group_dfs(self, entity_groups, column_dict, is_planning):
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
                    if type(attribute_value) in {GJFloat, GJInteger, GJBinary}:
                        attribute_value = None
                    row_data.append(attribute_value)
                if is_planning:
                    row_data = [0] + row_data
                df_data.append(row_data)
            schema = ["sample_id"] + column_names if is_planning else column_names
            df = pl.DataFrame(data=df_data, schema=schema, orient="row")
            df_dict[df_name] = df
        return df_dict

