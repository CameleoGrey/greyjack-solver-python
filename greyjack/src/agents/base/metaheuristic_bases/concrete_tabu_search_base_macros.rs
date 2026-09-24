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
            ) -> PyResult<Self> {

                // The validated variables own semantic groups; the legacy group
                // argument remains accepted for Python call compatibility.
                let variables_manager = VariablesManager::new(variables_manager_py.variables_vec.clone());
                let mover = Mover::new(tabu_entity_rate, mutation_rate_multiplier, move_probas, &variables_manager)
                    .map_err(pyo3::exceptions::PyValueError::new_err)?;
                let group_mutation_rates_map = mover.group_mutation_rates_map.clone();
                let current_mutation_rate_multiplier = mutation_rate_multiplier.unwrap_or(0.0);

                if neighbours_count == 0 {
                    return Err(pyo3::exceptions::PyValueError::new_err("neighbours_count must be positive"));
                }
                Ok(Self {
                    neighbours_count: neighbours_count,
                    tabu_entity_rate: tabu_entity_rate,
                    metaheuristic_kind: "LocalSearch".to_string(),
                    metaheuristic_name: "TabuSearch".to_string(),
                    discrete_ids: discrete_ids.clone(),
                    mover,
                    variables_manager
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
                (0..self.neighbours_count).map(|_| {
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
                let deltas = (0..self.neighbours_count).map(|_| {
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
                ) -> (Vec<$individual_variant>, Option<Vec<(usize, f64)>>) {

                let best_score_id: usize = scores
                    .iter()
                    .enumerate()
                    .min_by(|(_, a), (_, b)| a.cmp(b))
                    .map(|(index, _)| index)
                    .unwrap();

                let mut sample = sample;
                let best_score = scores[best_score_id].clone();

                if best_score <= current_population[0].score {
                    let new_values = deltas[best_score_id].clone();
                    for (var_id, new_value) in &new_values {
                        sample[*var_id] = *new_value;
                    }
                    let best_candidate = $individual_variant::new(sample.clone(), best_score);
                    let new_population = vec![best_candidate; 1];

                    (new_population, Some(new_values))
                } else {
                    (current_population.clone(), None)
                }
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
