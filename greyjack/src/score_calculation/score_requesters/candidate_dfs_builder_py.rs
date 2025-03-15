



use polars::frame::DataFrame;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use crate::score_calculation::score_requesters::VariablesManager;
use crate::variables::GJPlanningVariablePy;
use crate::variables::GJPlanningVariable;
use crate::score_calculation::score_requesters::CandidateDfsBuilder;
use std:: collections::HashMap;
use std::string::String;

#[pyclass]
pub struct CandidateDfsBuilderPy {
    pub candidate_dfs_builder: CandidateDfsBuilder
}


#[pymethods]
impl CandidateDfsBuilderPy {

    #[new]
    pub fn new(
        variables_vec_py: Vec<GJPlanningVariablePy>, 
        var_name_to_vec_id_map: HashMap<String, usize>, 
        vec_id_to_var_name_map: HashMap<usize, String>,
        planning_entities_column_map: HashMap<String, Vec<String>>,
        problem_facts_column_map: HashMap<String, Vec<String>>,
        planning_entity_dfs_py: HashMap<String, PyDataFrame>,
        problem_fact_dfs_py: HashMap<String, PyDataFrame>,
        entity_is_int_map: HashMap<String, bool>,
    ) -> Self {

        let variables_vec: Vec<GJPlanningVariable> = variables_vec_py.iter().map(|var_py| {
            GJPlanningVariable::new(
                var_py.name.clone(), 
                var_py.lower_bound, 
                var_py.upper_bound, 
                var_py.frozen, 
                var_py.is_int, 
                var_py.initial_value, 
                Some(var_py.semantic_groups.clone()),
            )
        }).collect();

        let mut planning_entity_dfs: HashMap<String, DataFrame> = HashMap::new();
        planning_entity_dfs_py.iter().for_each(|(df_name, pydf)| {
            planning_entity_dfs.insert(df_name.clone(), pydf.clone().into());
        });

        let mut problem_fact_dfs: HashMap<String, DataFrame> = HashMap::new();
        problem_fact_dfs_py.iter().for_each(|(df_name, pydf)| {
            problem_fact_dfs.insert(df_name.clone(), pydf.clone().into());
        });

        let candidate_dfs_builder = CandidateDfsBuilder {
            planning_entities_column_map: planning_entities_column_map,
            problem_facts_column_map: problem_facts_column_map,
            planning_entity_dfs: planning_entity_dfs.clone(),
            problem_fact_dfs: problem_fact_dfs,
            raw_dfs: planning_entity_dfs.clone(),
            entity_is_int_map: entity_is_int_map,
            
            variables_manager: VariablesManager::new(variables_vec),

            var_name_to_df_col_names: HashMap::new(),
            var_name_to_vec_id_map: var_name_to_vec_id_map,
            vec_id_to_var_name_map: vec_id_to_var_name_map,
            df_column_to_var_ids_map: HashMap::new(),
            var_id_to_df_column_index_map: Vec::new(),
            var_id_to_df_name: Vec::new(),
            var_id_to_col_name: Vec::new(),

            cached_sample_id_vectors: HashMap::new(),
            cached_sample_size: 999_999_999

        };

        Self {
            candidate_dfs_builder: candidate_dfs_builder
        }

    }

    pub fn get_plain_candidate_dfs(&mut self, samples: Vec<Vec<f64>>) -> (HashMap<String, PyDataFrame>, HashMap<String, PyDataFrame>) {

        let (planning_entity_dfs, problem_fact_dfs) = self.candidate_dfs_builder.get_plain_candidate_dfs(&samples);
        
        let mut planning_entity_dfs_py: HashMap<String, PyDataFrame> = HashMap::new();
        planning_entity_dfs.iter().for_each(|(df_name, df)| {
            planning_entity_dfs_py.insert(df_name.clone(), PyDataFrame(df.clone()));
        });

        let mut problem_fact_dfs_py: HashMap<String, PyDataFrame> = HashMap::new();
        problem_fact_dfs.iter().for_each(|(df_name, df)| {
            problem_fact_dfs_py.insert(df_name.clone(), PyDataFrame(df.clone()));
        });

        return (planning_entity_dfs_py, problem_fact_dfs_py);
    }

    pub fn get_incremental_candidate_dfs(
        &mut self, 
        sample: Vec<f64>, 
        deltas: Vec<Vec<(usize, f64)>>
    ) -> (HashMap<String, PyDataFrame>, HashMap<String, PyDataFrame>, HashMap<String, PyDataFrame>) {
        
        let (planning_entity_dfs, problem_fact_dfs, delta_dfs) = self.candidate_dfs_builder.get_incremental_candidate_dfs(&sample, &deltas);

        let mut planning_entity_dfs_py: HashMap<String, PyDataFrame> = HashMap::new();
        planning_entity_dfs.iter().for_each(|(df_name, df)| {
            planning_entity_dfs_py.insert(df_name.clone(), PyDataFrame(df.clone()));
        });

        let mut problem_fact_dfs_py: HashMap<String, PyDataFrame> = HashMap::new();
        problem_fact_dfs.iter().for_each(|(df_name, df)| {
            problem_fact_dfs_py.insert(df_name.clone(), PyDataFrame(df.clone()));
        });

        let mut delta_dfs_py: HashMap<String, PyDataFrame> = HashMap::new();
        delta_dfs.iter().for_each(|(df_name, df)| {
            delta_dfs_py.insert(df_name.clone(), PyDataFrame(df.clone()));
        });

        return (planning_entity_dfs_py, problem_fact_dfs_py, delta_dfs_py);
    }

}