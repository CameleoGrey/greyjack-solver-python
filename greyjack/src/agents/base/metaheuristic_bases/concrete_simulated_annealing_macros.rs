#[macro_export]
macro_rules! build_concrete_simulated_annealing_base {
    ($me_base_name: ident, $individual_variant: ident, $score_type: ty) => {
        #[pyclass]
        pub struct $me_base_name{

            pub initial_temperature: Vec<f64>,
            pub cooling_rate: f64,
            pub tabu_entity_rate: f64,

            pub metaheuristic_kind: String,
            pub metaheuristic_name: String,

            pub group_mutation_rates_map: HashMap<String, f64>,
            pub discrete_ids: Option<Vec<usize>>,
            pub mover: Mover,
            pub variables_manager: VariablesManager,

            pub current_temperature: Vec<f64>,
            pub inverted_accomplish_rate: f64,
            pub random_sampler: Uniform<f64>,
            pub random_generator: StdRng,
            pub exp: f64,
        }

        #[pymethods]
        impl $me_base_name  {

            #[new]
            #[pyo3(signature = (variables_manager_py, initial_temperature, tabu_entity_rate, semantic_groups_dict, cooling_rate, mutation_rate_multiplier=None, move_probas=None, discrete_ids=None))]
            pub fn new(
                variables_manager_py: VariablesManagerPy,
                initial_temperature: Vec<f64>,
                tabu_entity_rate: f64,
                semantic_groups_dict: HashMap<String, Vec<usize>>,
                cooling_rate: f64,
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
                    initial_temperature: initial_temperature.clone(),
                    cooling_rate: cooling_rate,
                    tabu_entity_rate: tabu_entity_rate,

                    metaheuristic_kind: "LocalSearch".to_string(),
                    metaheuristic_name: "SimulatedAnnealing".to_string(),

                    group_mutation_rates_map: group_mutation_rates_map.clone(),
                    discrete_ids: discrete_ids.clone(),
                    mover,
                    variables_manager,
                    current_temperature: initial_temperature,
                    inverted_accomplish_rate: 1.0,
                    random_sampler: Uniform::new_inclusive(0.0, 1.0),
                    random_generator: StdRng::from_entropy(),
                    exp: 2.7182818284590452
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
                candidates: Vec<$individual_variant>
                ) -> Vec<$individual_variant> {

                self.current_temperature = self.current_temperature.iter().map(|ct| {
                    let mut new_temperature = *ct * self.cooling_rate;
                    if new_temperature < 0.000001 {
                        new_temperature = 0.0000001;
                    }
                    return new_temperature;
                }).collect();

                let current_energy = current_population[0].score.as_list();
                let candidate_energy = candidates[0].score.as_list();
                let accept_probas: Vec<f64> = current_energy
                .iter().zip(candidate_energy.iter())
                .enumerate()
                .map(|(i, (cur_e, can_e))| self.exp.powf(-((can_e - cur_e) / self.current_temperature[i])))
                .collect();

                let accept_proba = accept_probas.iter().fold(1.0, |acc, x| acc * *x);
                let random_value = self.random_sampler.sample(&mut self.random_generator);

                let new_population: Vec<$individual_variant>;
                if (candidates[0].score <= current_population[0].score) || (random_value < accept_proba) {
                    new_population = candidates.clone();
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

                self.current_temperature = self.current_temperature.iter().map(|ct| {
                    let mut new_temperature = *ct * self.cooling_rate;
                    if new_temperature < 0.000001 {
                        new_temperature = 0.0000001;
                    }
                    return new_temperature;
                }).collect();


                let current_energy = current_population[0].score.as_list();
                let candidate_energy = scores[0].as_list();
                let accept_probas: Vec<f64> = current_energy
                .iter().zip(candidate_energy.iter())
                .enumerate()
                .map(|(i, (cur_e, can_e))| self.exp.powf(-((can_e - cur_e) / self.current_temperature[i])))
                .collect();

                let accept_proba = accept_probas.iter().fold(1.0, |acc, x| acc * *x);
                let random_value = self.random_sampler.sample(&mut self.random_generator);

                let mut sample = sample;
                if (scores[0] <= current_population[0].score) || (random_value < accept_proba) {
                    let candidate_deltas = deltas[0].clone();
                    for (var_id, new_value) in &candidate_deltas {
                        sample[*var_id] = *new_value;
                    }
                    let candidate = $individual_variant::new(sample.clone(), scores[0].clone());
                    let new_population = vec![candidate; 1];
                    (new_population, Some(candidate_deltas))
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
    }
}
