
from typing import Dict, List, Tuple, Any
import polars as pl
import numpy as np
from collections import defaultdict
from greyjack.score_calculation.score_requesters.VariablesManager import VariablesManager
from greyjack.greyjack import GJPlanningVariablePy, VariablesManagerPy
from greyjack.variables import *

# mostly rewrited by LLM from Rust to Python


from typing import Dict, List, Tuple, Any
import polars as pl
import numpy as np
from collections import defaultdict
from greyjack.score_calculation.score_requesters.VariablesManager import VariablesManager
from greyjack.greyjack import GJPlanningVariablePy, VariablesManagerPy, CandidateDfsBuilderPy
from greyjack.variables import *

# mostly rewrited by LLM from Rust to Python 
class OOPScoreRequester:
    def __init__(self, cotwin):
        self.cotwin = cotwin

        self.available_planning_variable_types = {GJFloat, GJInteger, GJBinary}
        variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map = self.build_variables_info(self.cotwin)
        self.variables_manager = VariablesManagerPy(variables_vec)
        planning_entities_column_map = self.build_column_map(self.cotwin.planning_entities)
        problem_facts_column_map = self.build_column_map(self.cotwin.problem_facts)
        planning_entity_dfs = self.build_group_dfs(self.cotwin.planning_entities, planning_entities_column_map, True)
        problem_fact_dfs = self.build_group_dfs(self.cotwin.problem_facts, problem_facts_column_map, False)

        self.candidate_dfs_builder = CandidateDfsBuilderPy(
            variables_vec,
            var_name_to_vec_id_map, 
            vec_id_to_var_name_map,
            planning_entities_column_map,
            problem_facts_column_map,
            planning_entity_dfs,
            problem_fact_dfs
        )

    # mostly from prototype
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

    def request_score_plain(self, samples):

        planning_entity_dfs, problem_fact_dfs = self.candidate_dfs_builder.get_plain_candidate_dfs(samples)
        score_batch = self.cotwin.get_score(planning_entity_dfs, problem_fact_dfs)
        return score_batch

    def request_score_incremental(self, sample, deltas):

        planning_entity_dfs, problem_fact_dfs, delta_dfs = self.candidate_dfs_builder.get_incremental_candidate_dfs(sample, deltas)
        score_batch = self.cotwin.get_score(planning_entity_dfs, problem_fact_dfs, delta_dfs)
        return score_batch
 
