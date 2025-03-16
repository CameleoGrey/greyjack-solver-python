



use polars::prelude::*;
use crate::score_calculation::score_requesters::VariablesManager;
use crate::variables::GJPlanningVariable;

use std:: collections::HashMap;
use std::string::String;

pub struct CandidateDfsBuilder {
        pub variables_manager: VariablesManager,

        pub var_name_to_df_col_names: HashMap<String, (String, String)>,
        pub var_name_to_vec_id_map: HashMap<String, usize>,
        pub vec_id_to_var_name_map: HashMap<usize, String>,
        pub df_column_to_var_ids_map: HashMap<(String, String), Vec<usize>>,
        pub var_id_to_df_column_index_map: Vec<(String, String, usize)>,
        pub var_id_to_df_name: Vec<String>,
        pub var_id_to_col_name: Vec<String>,
        
        pub cached_sample_id_vectors: HashMap<String, Vec<f64>>,
        pub cached_sample_size: usize,

        pub planning_entities_column_map: HashMap<String, Vec<String>>,
        pub problem_facts_column_map: HashMap<String, Vec<String>>,
        pub planning_entity_dfs: HashMap<String, DataFrame>,
        pub problem_fact_dfs: HashMap<String, DataFrame>,
        pub raw_dfs: HashMap<String, DataFrame>,
        pub entity_is_int_map: HashMap<String, bool>,
}

impl CandidateDfsBuilder {

        pub fn new(
            variables_vec: Vec<GJPlanningVariable>, 
            var_name_to_vec_id_map: HashMap<String, usize>, 
            vec_id_to_var_name_map: HashMap<usize, String>,
            planning_entities_column_map: HashMap<String, Vec<String>>,
            problem_facts_column_map: HashMap<String, Vec<String>>,
            planning_entity_dfs: HashMap<String, DataFrame>,
            problem_fact_dfs: HashMap<String, DataFrame>,
            entity_is_int_map: HashMap<String, bool>,
        ) -> Self {

            let score_requester = Self {
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

            return score_requester;
        }


        fn update_dfs_for_scoring(&mut self, group_data_map: &HashMap<String, HashMap<String, Vec<f64>>>, samples_count: usize, add_row_index: bool) {

            for df_name in group_data_map.keys() {
                let mut current_df = self.planning_entity_dfs[df_name].clone();
                let needful_rows_count  = samples_count * self.raw_dfs[df_name].size();
                if current_df.size() != needful_rows_count {
                    let mut new_df_parts: Vec<LazyFrame> = Vec::new();
                    for i in 0..samples_count {
                        new_df_parts.push(self.raw_dfs[df_name].clone().lazy());
                    }
                    current_df = concat(new_df_parts, UnionArgs::default()).unwrap().collect().unwrap();
                }

                for column_name in group_data_map[df_name].keys() {
                    current_df.drop_in_place(column_name).unwrap();
                    let updated_column_data = &group_data_map[df_name][column_name];
                    let mut updated_column = Series::new(column_name.into(), updated_column_data);
                    if self.entity_is_int_map.contains_key(column_name) {
                        if *self.entity_is_int_map.get(column_name).unwrap() {
                            updated_column = updated_column.cast(&DataType::Int64).unwrap();
                        }
                    } else if column_name.eq("sample_id") {
                        // using Int64 instead UInt64 because Python converts UInt64 to float
                        updated_column = updated_column.cast(&DataType::Int64).unwrap();
                    }


                    current_df.with_column(updated_column).unwrap();
                }
                current_df.rechunk_mut();

                if add_row_index == true {
                    current_df = current_df.with_row_index("candidate_df_row_id".into(), None).unwrap();
                }

                self.planning_entity_dfs.insert(df_name.clone(), current_df.clone());
            }

        }

        fn get_df_column_name(variable_name: String) -> (String, String) {

            let df_name:Vec<&str> = variable_name.split(": ").collect();
            let df_name = df_name[0].to_string();

            let column_name:Vec<&str> = variable_name.split("-->").collect();
            let column_name = column_name[column_name.len() - 1].to_string();

            return (df_name, column_name);
        }

        fn build_var_mappings(&mut self) -> HashMap<(String, String), Vec<usize>> {
            let variable_names= self.variables_manager.get_variables_names_vec();
            let mut df_column_var_ids: HashMap<(String, String), Vec<usize>> = HashMap::new();
            variable_names.iter().enumerate().for_each(|(i, var_name)| {
                let (df_name, column_name) = &Self::get_df_column_name(var_name.clone());

                self.var_id_to_df_name.push(df_name.clone());
                self.var_id_to_col_name.push(column_name.clone());

                if df_column_var_ids.contains_key(&(df_name.clone(), column_name.clone())) == false {
                    df_column_var_ids.insert((df_name.clone(), column_name.clone()), Vec::new());
                }
                    
                df_column_var_ids.get_mut(&(df_name.clone(), column_name.clone())).unwrap().push(i);

            });

            return df_column_var_ids;
        }

        fn build_group_data_map(&mut self, samples_vec: &Vec<Vec<f64>>, include_sample_id_column: bool) -> HashMap<String, HashMap<String, Vec<f64>>> {

            //let start_time = chrono::Utc::now().timestamp_millis();
            if self.df_column_to_var_ids_map.len() == 0 {
                self.df_column_to_var_ids_map = self.build_var_mappings();
            }

            let mut group_data_map: HashMap<String, HashMap<String, Vec<f64>>> = HashMap::new();

            for (df_name, col_name) in self.df_column_to_var_ids_map.keys() {
                if group_data_map.contains_key(df_name) == false {
                    group_data_map.insert(df_name.clone(), HashMap::new());
                }
                group_data_map.get_mut(df_name).unwrap().insert(col_name.clone(), Vec::new());
            }

            let _: () = self.df_column_to_var_ids_map.iter().map(|(df_col_name, var_ids)| {
                let _: () = samples_vec.iter().map(|sample_vec| {
                    let mut current_sample_column: Vec<f64> = var_ids.iter().map(|i| sample_vec[*i].clone()).collect();
                    group_data_map
                    .get_mut(&df_col_name.0).unwrap()
                    .get_mut(&df_col_name.1).unwrap()
                    .append(&mut current_sample_column);
                }).collect();
            }).collect();

            //let start_time = chrono::Utc::now().timestamp_millis();
            // add correct sample ids
            if include_sample_id_column == true {
                if samples_vec.len() != self.cached_sample_size {
                    let df_names: Vec<String> = group_data_map.keys().map(|x| x.clone()).collect();
                    for df_name in df_names {
                        let group_keys = group_data_map.get(&df_name).unwrap().keys().into_vec();
                        let first_group_key = group_keys.get(0).unwrap().as_str();
                        let updated_df_column_len = group_data_map.get(&df_name).unwrap().get(first_group_key).unwrap().len();
                        let samples_count = samples_vec.len();
                        let true_df_len = updated_df_column_len / samples_count;
                        let mut correct_sample_ids: Vec<f64> = Vec::new();
                        for i in 0..samples_count {
                            for j in 0..true_df_len {
                                correct_sample_ids.push(i as f64);
                            }
                        }

                        self.cached_sample_size = samples_vec.len();
                        self.cached_sample_id_vectors.insert(
                            df_name.clone(), 
                            correct_sample_ids.iter().map(|vec_value| {
                                vec_value.clone() as f64
                            }).collect());

                        group_data_map.get_mut(&df_name).unwrap().insert("sample_id".to_string(), correct_sample_ids);
                    }
                } else {
                    for df_name in self.cached_sample_id_vectors.keys() {
                        group_data_map.get_mut(df_name).unwrap().insert(
                            "sample_id".to_string(), 
                            self.cached_sample_id_vectors.get(df_name).unwrap().iter().map(|x| *x as f64).collect()
                        );
                    }
                }
            }

            return group_data_map;

        }

        pub fn build_var_id_to_df_column_index_map(&mut self) -> Vec<(String, String, usize)> {

            let mut var_id_to_df_column_index_map: Vec<(String, String, usize)> = Vec::new();
            let mut increment_row_id_map: HashMap<(&String, &String), usize> = HashMap::new();

            var_id_to_df_column_index_map = 
            self.var_id_to_df_name
            .iter()
            .zip(self.var_id_to_col_name.iter())
            .enumerate()
            .map(|(var_id, (df_name, col_name))| {

                if increment_row_id_map.contains_key(&(df_name, col_name)) {
                    *increment_row_id_map.get_mut(&(df_name, col_name)).unwrap() += 1;
                } else {
                    increment_row_id_map.insert((df_name, col_name), 0);
                }

                let current_row_id = *increment_row_id_map.get(&(df_name, col_name)).unwrap();
                return (df_name.clone(), col_name.clone(), current_row_id);

            })
            .collect();

            return var_id_to_df_column_index_map;
        }

        pub fn build_delta_dfs(
            &mut self, 
            group_data_map: &HashMap<String, HashMap<String, Vec<f64>>>, 
            inverted_deltas: Vec<Vec<(usize, f64)>>
        ) -> HashMap<String, DataFrame> {

            if self.var_id_to_df_column_index_map.len() == 0 {
                self.var_id_to_df_column_index_map = self.build_var_id_to_df_column_index_map();
            }

            let mut delta_data_map: HashMap<String, HashMap<String, Vec<f64>>> = HashMap::new();
            (0..inverted_deltas.len()).into_iter().for_each(|sample_id| {

                let current_sample_deltas = inverted_deltas[sample_id].clone();
                current_sample_deltas.iter().for_each(|(var_id, new_value)| {

                    let (df_name, var_col_name, row_id) = self.var_id_to_df_column_index_map[*var_id].clone();
                    if delta_data_map.contains_key(&df_name) == false {
                        delta_data_map.insert(df_name.clone(), HashMap::new());
                        delta_data_map.get_mut(&df_name).unwrap().insert("sample_id".to_string(), Vec::new());
                        delta_data_map.get_mut(&df_name).unwrap().insert("candidate_df_row_id".to_string(), Vec::new());
                    }

                    delta_data_map.get_mut(&df_name).unwrap().get_mut("sample_id").unwrap().push(sample_id as f64);
                    delta_data_map.get_mut(&df_name).unwrap().get_mut("candidate_df_row_id").unwrap().push(row_id as f64);

                    let current_df_column_data = group_data_map.get(&df_name).unwrap();
                    current_df_column_data.iter().for_each(|(column_name, column_values)| {
                        if delta_data_map.get(&df_name).unwrap().contains_key(column_name) == false {
                            delta_data_map.get_mut(&df_name).unwrap().insert(column_name.clone(), Vec::new());
                        }

                        if column_name.eq(&var_col_name) {
                            delta_data_map.get_mut(&df_name).unwrap().get_mut(column_name).unwrap().push(new_value.clone());
                        } else {
                            delta_data_map.get_mut(&df_name).unwrap().get_mut(column_name).unwrap().push(column_values[row_id].clone());
                        }
                    });
                });
            });

            let mut delta_dfs: HashMap<String, DataFrame> = HashMap::new();
            delta_data_map.keys().into_iter().for_each(|df_name| {

                let mut current_df = DataFrame::empty();
                delta_data_map[df_name].keys().into_iter().for_each(|column_name| {

                    let updated_column_data = &delta_data_map[df_name][column_name];
                    let mut updated_column = Series::new(column_name.into(), updated_column_data);

                    if self.entity_is_int_map.contains_key(column_name) {
                        if *self.entity_is_int_map.get(column_name).unwrap() {
                            updated_column = updated_column.cast(&DataType::Int64).unwrap();
                        }
                    } else if column_name.eq("sample_id") {
                        // using Int64 instead UInt64 because Python converts UInt64 to float
                        updated_column = updated_column.cast(&DataType::Int64).unwrap();
                    } else if column_name.eq("candidate_df_row_id") {
                        // using Int64 instead UInt64 because Python converts UInt64 to float
                        updated_column = updated_column.cast(&DataType::Int64).unwrap();
                    }


                    current_df.with_column(updated_column).unwrap();
                });
                current_df = current_df.sort(["sample_id", "candidate_df_row_id"], SortMultipleOptions::default()).unwrap();

                delta_dfs.insert(df_name.clone(), current_df);
            });

            return delta_dfs;
        }

        pub fn get_plain_candidate_dfs(&mut self, samples: &Vec<Vec<f64>>) -> (HashMap<String, DataFrame>, HashMap<String, DataFrame>) {

            let group_data_map = self.build_group_data_map(samples, true);
            let samples_count = samples.len();
            self.update_dfs_for_scoring(&group_data_map, samples_count, false);

            return (self.planning_entity_dfs.clone(), self.problem_fact_dfs.clone());
        }

        pub fn get_incremental_candidate_dfs(
            &mut self, 
            sample: &Vec<f64>, 
            deltas: &Vec<Vec<(usize, f64)>>
        ) -> (HashMap<String, DataFrame>, HashMap<String, DataFrame>, HashMap<String, DataFrame>) {

            let group_data_map = self.build_group_data_map(&vec![sample.clone(); 1], false);
            self.update_dfs_for_scoring(&group_data_map, 1, true);
            let delta_dfs = self.build_delta_dfs(&group_data_map, deltas.clone());

            return (self.planning_entity_dfs.clone(), self.problem_fact_dfs.clone(), delta_dfs);
        }

    }