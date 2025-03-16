
import polars as pl
from greyjack.greyjack import VariablesManagerPy, CandidateDfsBuilderPy
from greyjack.variables.GJFloat import GJFloat
from greyjack.variables.GJInteger import GJInteger
from greyjack.variables.GJBinary import GJBinary

class OOPScoreRequester:
    def __init__(self, cotwin):
        self.cotwin = cotwin

        self.available_planning_variable_types = {GJFloat, GJInteger, GJBinary}
        variables_vec, var_name_to_vec_id_map, vec_id_to_var_name_map = self.build_variables_info(self.cotwin)
        self.variables_manager = VariablesManagerPy(variables_vec)
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

    def build_column_map(self, entity_groups):
        
        column_dict = {}
        entity_is_int_map = {}
        for group_name in entity_groups:
            column_dict[group_name] = []
            entity_objects = entity_groups[group_name]
            sample_object = entity_objects[0]
            object_attributes = sample_object.__dict__
            for attribute_name in object_attributes:
                column_dict[group_name].append( attribute_name )
                attribute_value = object_attributes[attribute_name]
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
        score_batch = self.cotwin.get_score_plain(planning_entity_dfs, problem_fact_dfs)
        return score_batch

    def request_score_incremental(self, sample, deltas):

        planning_entity_dfs, problem_fact_dfs, delta_dfs = self.candidate_dfs_builder.get_incremental_candidate_dfs(sample, deltas)
        score_batch = self.cotwin.get_score_incremental(planning_entity_dfs, problem_fact_dfs, delta_dfs)
        return score_batch
 
