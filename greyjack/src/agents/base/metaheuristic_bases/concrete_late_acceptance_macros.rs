#[macro_export]
macro_rules! build_concrete_late_acceptance_base {

    ($me_base_name: ident, $individual_variant: ident, $score_type: ty) => {
        #[pyclass]
        pub struct $me_base_name {

            pub late_acceptance_size: usize,
            pub late_scores: VecDeque<$score_type>,
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
            #[pyo3(signature = (variables_manager_py, late_acceptance_size, tabu_entity_rate, semantic_groups_map, mutation_rate_multiplier=None, move_probas=None, discrete_ids=None))]
            pub fn new(
                variables_manager_py: VariablesManagerPy,
                late_acceptance_size: usize,
                tabu_entity_rate: f64,
                semantic_groups_map: HashMap<String, Vec<usize>>,
                mutation_rate_multiplier: Option<f64>,
                move_probas: Option<Vec<f64>>,
                discrete_ids: Option<Vec<usize>>,
            ) -> PyResult<Self> {

                // The validated variables own semantic groups; the legacy group
                // argument remains accepted for Python call compatibility.
                let variables_manager = VariablesManager::new(variables_manager_py.variables_vec.clone());
                let mover = Mover::new(tabu_entity_rate, mutation_rate_multiplier, move_probas, &variables_manager)
                    .map_err(pyo3::exceptions::PyValueError::new_err)?;
                let group_mutation_rates_map = mover.group_mutation_rates_map.clone();
                let current_mutation_rate_multiplier = mutation_rate_multiplier.unwrap_or(0.0);

                Ok(Self {
                    late_acceptance_size: late_acceptance_size,
                    tabu_entity_rate: tabu_entity_rate,
                    late_scores: VecDeque::new(),


                    metaheuristic_kind: "LocalSearch".to_string(),
                    metaheuristic_name: "LateAcceptance".to_string(),

                    group_mutation_rates_map: group_mutation_rates_map.clone(),
                    discrete_ids: discrete_ids.clone(),
                    mover,
                    variables_manager,
                })
            }

            fn sample_candidates_plain(
                &mut self,
                population: Vec<$individual_variant>,
                current_top_individual: $individual_variant,
            ) -> PyResult<Vec<Vec<f64>>> {
                let candidate = &population.first()
                    .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Population must not be empty"))?
                    .variable_values;
                (0..1).map(|_| {
                    self.mover.sample_plain(candidate, &self.variables_manager)
                        .map_err(pyo3::exceptions::PyValueError::new_err)
                }).collect()
            }

            fn sample_candidates_incremental(
                &mut self,
                population: Vec<$individual_variant>,
                current_top_individual: $individual_variant,
            ) -> PyResult<(Vec<f64>, Vec<Vec<(usize, f64)>>)> {
                let candidate = &population.first()
                    .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Population must not be empty"))?
                    .variable_values;
                let deltas = (0..1).map(|_| {
                    self.mover.sample_delta(candidate, &self.variables_manager)
                        .map(|delta| delta.into_pairs())
                        .map_err(pyo3::exceptions::PyValueError::new_err)
                }).collect::<PyResult<Vec<_>>>()?;
                Ok((candidate.clone(), deltas))
            }

            fn build_updated_population(
                &mut self,
                current_population: Vec<$individual_variant>,
                candidates: Vec<$individual_variant>,
                ) -> Vec<$individual_variant> {

                let candidate_to_compare_score;
                if self.late_scores.len() == 0 {
                    candidate_to_compare_score = current_population[0].score.clone();
                } else {
                    candidate_to_compare_score = self.late_scores.back().unwrap().clone();
                }

                let new_population;
                let candidate_score = candidates[0].score.clone();
                if (candidate_score <= candidate_to_compare_score) || (candidate_score <= current_population[0].score) {
                    let best_candidate = candidates[0].clone();
                    new_population = vec![best_candidate; 1];
                    self.late_scores.push_front(candidate_score);
                    if self.late_scores.len() > self.late_acceptance_size {
                        self.late_scores.pop_back();
                    }
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
                ) -> (Vec<$individual_variant>, Option<Vec<(usize, f64)>>) {

                let late_native_score;
                if self.late_scores.len() == 0 {
                    late_native_score = current_population[0].score.clone();
                } else {
                    late_native_score = self.late_scores.back().unwrap().clone();
                }

                let candidate_score = scores[0].clone();

                let mut sample = sample;
                if (candidate_score <= late_native_score) || (candidate_score <= current_population[0].score) {
                    let best_deltas = deltas[0].clone();
                    for (var_id, new_value) in &best_deltas {
                        sample[*var_id] = *new_value;
                    }
                    let best_candidate = $individual_variant::new(sample.clone(), candidate_score.clone());
                    let new_population = vec![best_candidate; 1];
                    self.late_scores.push_front(candidate_score);
                    if self.late_scores.len() > self.late_acceptance_size {
                        self.late_scores.pop_back();
                    }
                    (new_population, Some(best_deltas))
                } else {
                    (current_population.clone(), None)
                }
            }

            #[getter]
            fn get_metaheuristic_kind(&self) -> String {
                self.metaheuristic_kind.clone()
            }

            #[getter]
            fn get_metaheuristic_name(&self) -> String {
                self.metaheuristic_name.clone()
            }

        }
    };
}
