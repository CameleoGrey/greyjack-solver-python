

#[macro_export]
macro_rules! build_concrete_genetic_algorithm_base {
    ($me_base_name: ident, $individual_variant: ident, $score_type: ty) => {
        #[pyclass]
        pub struct $me_base_name {

            pub population_size: usize,
            pub half_population_size: usize,
            pub crossover_probability: f64,
            pub mutation_rate_multiplier: f64,
            pub p_best_rate: f64,
            pub tabu_entity_rate: f64,

            pub metaheuristic_kind: String,
            pub metaheuristic_name: String,

            pub group_mutation_rates_map: HashMap<String, f64>,
            pub discrete_ids: Option<Vec<usize>>,
            pub mover: Mover,
            pub variables_manager: VariablesManager,
        }

        #[pymethods]
        impl $me_base_name {

            #[new]
            #[pyo3(signature = (variables_manager_py, population_size, 
                                crossover_probability, p_best_rate, tabu_entity_rate, 
                                semantic_groups_dict,
                                mutation_rate_multiplier=None, move_probas=None, discrete_ids=None))]
            pub fn new(
                variables_manager_py: VariablesManagerPy,
                population_size: usize, 
                crossover_probability: f64,
                p_best_rate: f64,
                tabu_entity_rate: f64,
                semantic_groups_dict: HashMap<String, Vec<usize>>,
                mutation_rate_multiplier: Option<f64>,
                move_probas: Option<Vec<f64>>,
                discrete_ids: Option<Vec<usize>>,
            ) -> Self {

                let half_population_size = (0.5 * (population_size as f64)).ceil() as usize;
                let current_mutation_rate_multiplier;
                match mutation_rate_multiplier {
                    Some(x) => current_mutation_rate_multiplier = mutation_rate_multiplier.unwrap(),
                    None => current_mutation_rate_multiplier = 0.0 // 0.0 - always use minimal possible move size, 1.0 - is more intuitive,
                }
                let mut group_mutation_rates_map: HashMap<String, f64> = HashMap::new();
                for group_name in semantic_groups_dict.keys() {
                    let group_size = semantic_groups_dict[group_name].len();
                    let current_group_mutation_rate = current_mutation_rate_multiplier * (1.0 / (group_size as f64));
                    group_mutation_rates_map.insert(group_name.clone(), current_group_mutation_rate);
                }

                Self {
                    population_size: population_size,
                    half_population_size: half_population_size,
                    crossover_probability: crossover_probability,
                    mutation_rate_multiplier: current_mutation_rate_multiplier,
                    p_best_rate: p_best_rate,
                    tabu_entity_rate: tabu_entity_rate,

                    metaheuristic_kind: "Population".to_string(),
                    metaheuristic_name: "GeneticAlgorithm".to_string(),

                    group_mutation_rates_map: group_mutation_rates_map.clone(),
                    discrete_ids: discrete_ids.clone(),
                    mover: Mover::new(tabu_entity_rate, HashMap::new(), HashMap::new(), HashMap::new(), group_mutation_rates_map.clone(), move_probas),
                    variables_manager: VariablesManager::new(variables_manager_py.variables_vec.clone()),
                }
            }

            fn select_p_best_id(&mut self) -> usize {

                let p_best_proba = Uniform::new(0.000001, self.p_best_rate).sample(&mut StdRng::from_entropy());
                let last_top_id = (p_best_proba * (self.population_size as f64)).ceil() as usize;
                let chosen_id:usize = Uniform::new(0, last_top_id).sample(&mut StdRng::from_entropy());

                return chosen_id;
            }

            fn select_p_worst_id(&mut self) -> usize {

                let p_best_proba = Uniform::new(0.000001, self.p_best_rate).sample(&mut StdRng::from_entropy());
                let last_top_id = (p_best_proba * (self.population_size as f64)).ceil() as usize;
                let chosen_id: usize = Uniform::new(self.population_size - last_top_id, self.population_size).sample(&mut StdRng::from_entropy());

                return chosen_id;
            }

            fn cross(&mut self, candidate_1: Vec<f64>, candidate_2: Vec<f64>) -> (Vec<f64>, Vec<f64>) {

                let variables_count = candidate_1.len();
                let mut weights = vec![Uniform::new_inclusive(0.0, 1.0).sample(&mut StdRng::from_entropy()); variables_count];

                match &self.discrete_ids {
                    None => (),
                    Some(discrete_ids) => discrete_ids.into_iter().for_each(|i| weights[*i] = math_utils::rint(weights[*i]))
                }

                let new_candidate_1: Vec<f64> = 
                    weights.iter()
                    .zip(candidate_1.iter())
                    .zip(candidate_2.iter())
                    .map(|((w, c_1), c_2)| {
                        c_1 * w + c_2 * (1.0 - w)
                    })
                    .collect();

                let new_candidate_2: Vec<f64> = 
                    weights.iter()
                    .zip(candidate_1.iter())
                    .zip(candidate_2.iter())
                    .map(|((w, c_1), c_2)| {
                        c_2 * w + c_1 * (1.0 - w)
                    })
                    .collect();

                return (new_candidate_1, new_candidate_2);
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
                        self.mover.tabu_entity_size_map.insert(group_name.clone(), max((self.tabu_entity_rate * (group_ids.len() as f64)).ceil() as usize, 1));
                        self.mover.tabu_ids_vecdeque_map.insert(group_name.clone(), VecDeque::new());
                    }
                }
                
                let mut population = population;
                population.sort();

                let mut candidates: Vec<Vec<f64>> = Vec::new();
                for i in 0..self.half_population_size {
                    let mut candidate_1 = population[self.select_p_best_id()].variable_values.clone();
                    let mut candidate_2 = population[self.select_p_best_id()].variable_values.clone();

                    if Uniform::new_inclusive(0.0, 1.0).sample(&mut StdRng::from_entropy()) <= self.crossover_probability {
                        (candidate_1, candidate_2) = self.cross(candidate_1, candidate_2);
                    }
                    
                    let (changed_candidate_1, changed_columns_1, _) = self.mover.do_move(&mut candidate_1, &self.variables_manager, false);
                    let (changed_candidate_2, changed_columns_2, _) = self.mover.do_move(&mut candidate_2, &self.variables_manager, false);

                    candidate_1 = changed_candidate_1.unwrap();
                    candidate_2 = changed_candidate_2.unwrap();


                    // for crossover with rint() one doesn't need for fixing the whole candidate vector
                    // float values are crossed without rint, but due to the convex sum they will be still into the bounds
                    // all sampled values are always in the bounds
                    // problems can occur only by swap mutations, so fix all changed by a move columns
                    self.variables_manager.fix_variables(&mut candidate_1, changed_columns_1);
                    self.variables_manager.fix_variables(&mut candidate_2, changed_columns_2);

                    candidates.push(candidate_1);
                    candidates.push(candidate_2);
                }
                
                return candidates;
            }

            fn sample_candidates_incremental(
                &mut self,
                population: Vec<$individual_variant>, 
                current_top_individual: $individual_variant,
            ) -> (Vec<f64>, Vec<Vec<(usize, f64)>>) {
                panic!("Incremental candidates sampling is available only for local search approaches (TabuSearch, LateAcceptance, etc).")
            }

            fn build_updated_population(
                &mut self, 
                current_population: Vec<$individual_variant>, 
                candidates: Vec<$individual_variant>
                ) -> Vec<$individual_variant> {
                
                let mut winners: Vec<$individual_variant> = Vec::new();
                for i in 0..self.population_size {
                    let chosen_id = self.select_p_worst_id();
                    let weak_native = current_population[chosen_id].clone();
                    let candidate = &candidates[i];
                    let winner = if &candidate.score <= &weak_native.score {candidate.clone()} else {weak_native.clone()};
                    winners.push(winner);
                }

                return winners;
            }

            fn build_updated_population_incremental(
                    &mut self, 
                    current_population: Vec<$individual_variant>, 
                    sample: Vec<f64>,
                    deltas: Vec<Vec<(usize, f64)>>,
                    scores: Vec<$score_type>,
                ) -> Vec<$individual_variant> {
                
                panic!("Incremental candidates sampling is available only for local search approaches (TabuSearch, LateAcceptance, etc).")
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