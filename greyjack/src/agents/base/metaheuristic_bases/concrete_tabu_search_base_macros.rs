

#[macro_export]
macro_rules! build_concrete_tabu_search_base {

    ($me_base_name: ident, $individual_variant: ident, $score_type: ty) => {
        #[pyclass]
        pub struct $me_base_name {

            pub neighbours_count: usize,
            pub tabu_entity_rate: f64,

            pub metaheuristic_kind: String,
            pub metaheuristic_name: String,

            pub discrete_ids: Option<Vec<usize>>,
            pub mover: Mover,
            pub variables_manager: VariablesManager,
        }

        #[pymethods]
        impl $me_base_name {

            #[new]
            #[pyo3(signature = (variables_manager_py, neighbours_count, tabu_entity_rate, semantic_groups_map, mutation_rate_multiplier=None, move_probas=None, discrete_ids=None))]
            pub fn new(
                variables_manager_py: VariablesManagerPy,
                neighbours_count: usize,
                tabu_entity_rate: f64,
                semantic_groups_map: HashMap<String, Vec<usize>>,
                mutation_rate_multiplier: Option<f64>,
                move_probas: Option<Vec<f64>>,
                discrete_ids: Option<Vec<usize>>,
            ) -> Self {

                let current_mutation_rate_multiplier;
                match mutation_rate_multiplier {
                    Some(x) => current_mutation_rate_multiplier = mutation_rate_multiplier.unwrap(),
                    None => current_mutation_rate_multiplier = 0.0,
                }
                let mut group_mutation_rates_map: HashMap<String, f64> = HashMap::new();
                for group_name in semantic_groups_map.keys() {
                    let group_size = semantic_groups_map[group_name].len();
                    let current_group_mutation_rate = current_mutation_rate_multiplier * (1.0 / (group_size as f64));
                    group_mutation_rates_map.insert(group_name.clone(), current_group_mutation_rate);
                }

                Self {
                    neighbours_count: neighbours_count,
                    tabu_entity_rate: tabu_entity_rate,
                    metaheuristic_kind: "LocalSearch".to_string(),
                    metaheuristic_name: "TabuSearch".to_string(),
                    discrete_ids: discrete_ids.clone(),
                    mover: Mover::new(tabu_entity_rate, HashMap::new(), HashMap::new(), HashMap::new(), group_mutation_rates_map, move_probas),
                    variables_manager: VariablesManager::new(variables_manager_py.variables_vec.clone())
                }
            }

            fn sample_candidates_plain(
                &mut self, 
                population: Vec<$individual_variant>, 
                current_top_individual: $individual_variant,
            ) -> Vec<Vec<f64>> {

                if self.mover.tabu_entity_size_map.len() == 0 {
                    let semantic_groups_map = self.variables_manager.semantic_groups_map.clone();
                    for (group_name, group_ids) in semantic_groups_map {
                        self.mover.tabu_ids_sets_map.insert(group_name.clone(), HashSet::new());
                        self.mover.tabu_entity_size_map.insert(group_name.clone(), max((self.tabu_entity_rate * (group_ids.len().to_f64().unwrap())).ceil() as usize, 1));
                        self.mover.tabu_ids_vecdeque_map.insert(group_name.clone(), VecDeque::new());
                    }
                }

                let current_best_candidate = population[0].variable_values.clone();
                let mut candidates: Vec<Vec<f64>> = (0..self.neighbours_count).into_iter().map(|i| {
                    let (changed_candidate, changed_columns, _) = self.mover.do_move(&current_best_candidate, &self.variables_manager, false);
                    let mut candidate = changed_candidate.unwrap();
                    self.variables_manager.fix_variables(&mut candidate, changed_columns);
                    candidate
                }).collect();

                return candidates;
            }

            fn sample_candidates_incremental(
                &mut self,
                population: Vec<$individual_variant>, 
                current_top_individual: $individual_variant,
            ) -> (Vec<f64>, Vec<Vec<(usize, f64)>>) {

                if self.mover.tabu_entity_size_map.len() == 0 {
                    let semantic_groups_map = self.variables_manager.semantic_groups_map.clone();
                    for (group_name, group_ids) in semantic_groups_map {
                        self.mover.tabu_ids_sets_map.insert(group_name.clone(), HashSet::new());
                        self.mover.tabu_entity_size_map.insert(group_name.clone(), max((self.tabu_entity_rate * (group_ids.len().to_f64().unwrap())).ceil() as usize, 1));
                        self.mover.tabu_ids_vecdeque_map.insert(group_name.clone(), VecDeque::new());
                    }
                }

                let current_best_candidate = population[0].variable_values.clone();
                let mut deltas: Vec<Vec<(usize, f64)>> = (0..self.neighbours_count).into_iter().map(|i| {

                    let (_, changed_columns, candidate_deltas) = self.mover.do_move(&current_best_candidate, &self.variables_manager, true);
                    let mut candidate_deltas = candidate_deltas.unwrap();
                    self.variables_manager.fix_deltas(&mut candidate_deltas, changed_columns.clone());
                    let changed_columns = changed_columns.unwrap();
                    let candidate_deltas: Vec<(usize, f64)> = changed_columns.iter().zip(candidate_deltas.iter()).map(|(col_id, delta_value)| (*col_id, *delta_value)).collect();
                    candidate_deltas
                }).collect();

                return (current_best_candidate.clone(), deltas);


            }

            fn build_updated_population(
                &mut self, 
                current_population: Vec<$individual_variant>, 
                candidates: Vec<$individual_variant>,
                ) -> Vec<$individual_variant> {
                
                let mut candidates = candidates;
                candidates.sort();
                let new_population:Vec<$individual_variant>;
                let best_candidate = candidates[0].clone();
                if best_candidate.score <= current_population[0].score {
                    new_population = vec![best_candidate; 1];
                } else {
                    new_population = current_population.clone();
                }

                return new_population;
            }

            fn build_updated_population_incremental(
                    &mut self, 
                    current_population: Vec<$individual_variant>, 
                    sample: Vec<f64>,
                    deltas: Vec<Vec<(usize, f64)>>,
                    scores: Vec<$score_type>,
                ) -> Vec<$individual_variant> {
                

                let best_score_id: usize = scores
                    .iter()
                    .enumerate()
                    .min_by(|(_, a), (_, b)| a.cmp(b))
                    .map(|(index, _)| index)
                    .unwrap();
                let mut sample = sample;
                let best_score = scores[best_score_id].clone();    
                let new_population:Vec<$individual_variant>;
                if best_score <= current_population[0].score {
                    let best_deltas = &deltas[best_score_id];
                    for (var_id, new_value) in best_deltas {
                        sample[*var_id] = *new_value;
                    }
                    let best_candidate = $individual_variant::new(sample.clone(), best_score);
                    new_population = vec![best_candidate; 1];
                } else {
                    new_population = current_population.clone();
                }

                return new_population;
            }

            #[getter]
            pub fn metaheuristic_kind(&self) -> String {
                self.metaheuristic_kind.clone()
            }

            #[getter]
            pub fn metaheuristic_name(&self) -> String {
                self.metaheuristic_name.clone()
            }
        }
    };
}