/// Enumerate valid donor slots once instead of retrying random draws forever.
pub(crate) fn eligible_donor_indices<'a>(
    candidates: impl IntoIterator<Item = &'a [f64]>,
    first: &[f64],
    current: &[f64],
) -> Vec<usize> {
    candidates
        .into_iter()
        .enumerate()
        .filter_map(|(index, candidate)| {
            (candidate != first && candidate != current).then_some(index)
        })
        .collect()
}

#[macro_export]
macro_rules! build_concrete_lshade_base {
    ($me_base_name: ident, $individual_variant: ident, $score_type: ty) => {
        #[pyclass]
        pub struct $me_base_name {

            pub population_size: usize,
            pub history_archive_size: usize,
            pub initial_f: f64,
            pub initial_cr: f64,
            pub initial_mutation_proba: f64,
            pub mutation_rate_multiplier: f64,
            pub p_best_rate: f64,
            pub memory_pruning_rate: f64,
            pub guarantee_of_change_size: usize,

            pub history_archive: Vec<$individual_variant>,
            pub adaptive_f: Vec<f64>,
            pub adaptive_cr: Vec<f64>,
            pub adaptive_mutation_proba: Vec<f64>,
            pub current_history_archive_size: usize,
            pub k: usize,
            pub minimal_history_size: usize,

            pub history_f: Vec<f64>,
            pub history_cr: Vec<f64>,
            pub history_cr_ids: Vec<usize>,
            pub generated_f_list: Vec<f64>,
            pub generated_cr_list: Vec<f64>,
            pub previous_population_scores: Vec<$score_type>,

            pub tabu_entity_rate: f64,

            pub metaheuristic_kind: String,
            pub metaheuristic_name: String,

            pub group_mutation_rates_map: HashMap<String, f64>,
            pub discrete_ids: Option<Vec<usize>>,
            pub mover: Mover,
            pub variables_manager: VariablesManager,

            pub random_generator: StdRng,
        }

        #[pymethods]
        impl $me_base_name {

            #[new]
            #[pyo3(signature = (variables_manager_py, population_size, history_archive_size, p_best_rate, memory_pruning_rate, guarantee_of_change_size,
                                initial_f, initial_cr, initial_mutation_proba, tabu_entity_rate, semantic_groups_dict,
                                mutation_rate_multiplier, move_probas, discrete_ids))]
            pub fn new(
                variables_manager_py: VariablesManagerPy,
                population_size: usize,
                history_archive_size: usize,
                p_best_rate: f64,
                memory_pruning_rate: f64,
                guarantee_of_change_size: usize,
                initial_f: f64,
                initial_cr: f64,
                initial_mutation_proba: f64,
                tabu_entity_rate: f64,
                semantic_groups_dict: HashMap<String, Vec<usize>>,
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
                    population_size: population_size,
                    history_archive_size: history_archive_size,
                    initial_f: initial_f,
                    initial_cr: initial_cr,
                    initial_mutation_proba: initial_mutation_proba,
                    mutation_rate_multiplier: current_mutation_rate_multiplier,
                    p_best_rate: p_best_rate,
                    memory_pruning_rate: memory_pruning_rate,
                    guarantee_of_change_size: guarantee_of_change_size,

                    history_archive: Vec::new(),
                    adaptive_f: vec![initial_f; history_archive_size],
                    adaptive_cr: vec![initial_cr; history_archive_size],
                    adaptive_mutation_proba: vec![initial_mutation_proba; history_archive_size],
                    current_history_archive_size: history_archive_size,
                    k: 0,
                    minimal_history_size: 16, // from experiments. Lesser value will cause stucks due to possible situation of "no different vectors"

                    history_f: Vec::new(),
                    history_cr: Vec::new(),
                    history_cr_ids: Vec::new(),

                    generated_f_list: Vec::new(),
                    generated_cr_list: Vec::new(),
                    previous_population_scores: Vec::new(),

                    tabu_entity_rate: tabu_entity_rate,

                    metaheuristic_kind: "Population".to_string(),
                    metaheuristic_name: "LSHADE".to_string(),

                    group_mutation_rates_map: group_mutation_rates_map.clone(),
                    discrete_ids: discrete_ids.clone(),
                    mover,
                    variables_manager,
                    random_generator: StdRng::from_entropy(),
                })
            }


            // https://ru.wikipedia.org/wiki/%D0%A0%D0%B0%D1%81%D0%BF%D1%80%D0%B5%D0%B4%D0%B5%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5_%D0%9A%D0%BE%D1%88%D0%B8
            fn get_cauchy(&mut self, loc: f64, scale: f64) -> f64 {
                let uniform_value = self.random_generator.gen::<f64>();
                loc + scale * (PI * (uniform_value - 0.5)).tan()
            }

            fn sample_candidates_plain(
                &mut self,
                population: Vec<$individual_variant>,
                current_top_individual: &$individual_variant,
            ) -> PyResult<Vec<Vec<f64>>> {



                let mut population = population;
                population.sort();

                self.generated_f_list = vec![0.0; self.population_size];
                self.generated_cr_list = vec![0.0; self.population_size];
                self.previous_population_scores = population.iter().map(|ind| ind.score.clone()).collect();

                let mut candidates = Vec::with_capacity(self.population_size);

                for i in 0..self.population_size {
                    let random_id = self.random_generator.gen_range(0..self.adaptive_cr.len());
                    let current_cr = (Normal::new(self.adaptive_cr[random_id], 0.1).unwrap().sample(&mut self.random_generator)).clamp(0.0, 1.0);
                    let mutation_proba = (Normal::new(self.adaptive_mutation_proba[random_id], 0.1).unwrap().sample(&mut self.random_generator)).clamp(0.0, 1.0);

                    // LSHADE uses technique from JADE
                    let mut current_f = -1.0;
                    while current_f <= 0.0 {
                        current_f = self.get_cauchy(self.adaptive_f[random_id], 0.1);
                        current_f = current_f.min(1.0);
                    }

                    self.generated_cr_list[i] = current_cr;
                    self.generated_f_list[i] = current_f;

                    let p_best_proba = self.random_generator.gen_range(0.00001..self.p_best_rate);
                    let last_top_id = (p_best_proba * self.population_size as f64).ceil() as usize;
                    let p_best_vector = &population[self.random_generator.gen_range(0..last_top_id)].variable_values;
                    let current_vector = &population[i].variable_values;

                    let united_population: Vec<&$individual_variant> = population.iter().chain(self.history_archive.iter()).collect();

                    // chosing both vectors from united_population works better (less stucks in local minimums)
                    let random_vector_1 = &united_population[self.random_generator.gen_range(0..united_population.len())].variable_values;
                    let eligible = $crate::agents::base::metaheuristic_bases::concrete_lshade_macros::eligible_donor_indices(
                        united_population.iter().map(|individual| individual.variable_values.as_slice()),
                        random_vector_1, current_vector,
                    );
                    // A converged population can have no distinct donor. A zero
                    // differential term is valid; ordinary mutation can restore diversity.
                    let random_vector_2 = if eligible.is_empty() {
                        random_vector_1
                    } else {
                        &united_population[eligible[self.random_generator.gen_range(0..eligible.len())]].variable_values
                    };

                    let mut crossover_vector: Vec<f64> = current_vector.iter()
                        .zip(p_best_vector.iter())
                        .zip(random_vector_1.iter())
                        .zip(random_vector_2.iter())
                        .map(|(((x, p), r1), r2)| x + current_f * (p - x) + current_f * (r1 - r2))
                        .collect();

                    let (mut candidate_vector, changed_columns) =
                    if self.random_generator.gen::<f64>() < 0.5 {
                        let crossover_mask: Vec<bool> = (0..self.variables_manager.variables_count)
                            .map(|_| self.random_generator.gen::<f64>() < current_cr)
                            .collect();

                        let candidate: Vec<f64> = crossover_mask.iter()
                            .zip(current_vector.iter())
                            .zip(crossover_vector.iter())
                            .map(|((mask, curr), cross)| if *mask { *cross } else { *curr })
                            .collect();

                        let changed_columns: Vec<usize> = crossover_mask.iter()
                            .enumerate()
                            .filter(|(_, &mask)| mask)
                            .map(|(i, _)| self.variables_manager.variable_ids[i])
                            .collect();

                        let changed_columns =  if changed_columns.len() == 0 {None} else {Some(changed_columns)};

                        (candidate, changed_columns)

                    } else if self.random_generator.gen::<f64>() <= mutation_proba {
                        // my modification to prevent population degeneration and adapt LSHADE to mixed variable types cases
                        // take the whole crossover_vec and make mutation (move)
                        // p_best crossover changes all columns
                        let candidate = self.mover.sample_plain(&crossover_vector, &self.variables_manager)
                            .map_err(pyo3::exceptions::PyValueError::new_err)?;
                        let changed_columns: Vec<usize> = (0..crossover_vector.len()).collect();
                        (candidate, Some(changed_columns))
                    } else {
                        let crossover_mask: Vec<bool> = (0..self.variables_manager.variables_count)
                            .map(|_| self.random_generator.gen::<f64>() < current_cr)
                            .collect();

                        let candidate: Vec<f64> = crossover_mask.iter()
                            .zip(current_vector.iter())
                            .zip(crossover_vector.iter())
                            .map(|((mask, curr), cross)| if *mask { *cross } else { *curr })
                            .collect();

                        let changed_columns: Vec<usize> = crossover_mask.iter()
                            .enumerate()
                            .filter(|(_, &mask)| mask)
                            .map(|(i, _)| self.variables_manager.variable_ids[i])
                            .collect();

                        let changed_columns =  if changed_columns.len() == 0 {None} else {Some(changed_columns)};
                        (candidate, changed_columns)
                    };

                    let mut candidate_vector = candidate_vector;
                    if self.guarantee_of_change_size > 0 {
                        let current_change_count = self.random_generator.gen_range(1..=self.guarantee_of_change_size);
                        let columns_to_change: Vec<usize> = (0..self.variables_manager.variables_count).choose_multiple(&mut self.random_generator, current_change_count);

                        for &col in &columns_to_change {
                            candidate_vector[col] = crossover_vector[col];
                        }

                        self.variables_manager.fix_variables(&mut candidate_vector, Some(columns_to_change));
                    }
                    self.variables_manager.fix_variables(&mut candidate_vector, changed_columns);
                    candidates.push(candidate_vector);
                }

                return Ok(candidates);
            }

            fn sample_candidates_incremental(
                &mut self,
                population: Vec<$individual_variant>,
                current_top_individual: &$individual_variant,
            ) -> (Vec<f64>, Vec<Vec<(usize, f64)>>) {
                panic!("Incremental candidates sampling is available only for local search approaches (TabuSearch, LateAcceptance, etc).")
            }

            fn build_updated_population(
                &mut self,
                current_population: Vec<$individual_variant>,
                candidates: Vec<$individual_variant>
                ) -> PyResult<Vec<$individual_variant>> {

                let mut new_population: Vec<$individual_variant> = Vec::new();

                // Fill history
                for i in 0..self.population_size {
                    if candidates[i].score.get_priority_score() < current_population[i].score.get_priority_score() {
                        self.history_archive.push(candidates[i].clone());
                        self.history_cr.push(self.generated_cr_list[i]);
                        self.history_f.push(self.generated_f_list[i]);
                        self.history_cr_ids.push(i);
                    }

                    if candidates[i].score.get_priority_score() <= current_population[i].score.get_priority_score() {
                        new_population.push(candidates[i].clone());
                    } else {
                        new_population.push(current_population[i].clone());
                    }
                }

                // Memory pruning
                let samples_to_remember = ((1.0 - self.memory_pruning_rate) * self.history_archive_size as f64).ceil() as usize;
                if self.history_archive.len() > self.current_history_archive_size {
                    let samples_to_forget_count = self.history_archive.len() - samples_to_remember;

                    if samples_to_forget_count > 0 {
                        let indices: Vec<usize> = (0..self.history_archive.len()).collect();
                        let chosen = indices.choose_multiple(&mut self.random_generator, samples_to_forget_count);
                        let to_remove: HashSet<_> = chosen.collect();

                        let mut pruned_archive = Vec::new();
                        let mut pruned_f = Vec::new();
                        let mut pruned_cr = Vec::new();
                        let mut pruned_cr_ids = Vec::new();

                        for i in 0..self.history_archive.len() {
                            if !to_remove.contains(&i) {
                                pruned_archive.push(self.history_archive[i].clone());
                                pruned_cr.push(self.history_cr[i]);
                                pruned_f.push(self.history_f[i]);
                                pruned_cr_ids.push(self.history_cr_ids[i]);
                            }
                        }

                        self.history_archive = pruned_archive;
                        self.history_cr = pruned_cr;
                        self.history_f = pruned_f;
                        self.history_cr_ids = pruned_cr_ids;
                    }
                }

                // inlined self.update_parameters()
                // Algorithm 1: Memory update algorithm in SHADE 1.1; Eq. (7), (8), (9)
                if !self.history_f.is_empty() && !self.history_cr.is_empty() {
                    let archive_size = self.history_cr.len();
                    let score_deltas: Vec<f64> = self.history_cr_ids.iter()
                        .map(|&i| {
                            let previous_score = self.previous_population_scores[i].get_priority_score();
                            let current_score = new_population[i].score.get_priority_score();
                            (current_score - previous_score).abs()
                        })
                        .collect();

                    let sum_delta: f64 = score_deltas.iter().sum();
                    let weights: Vec<f64> = if sum_delta == 0.0 {
                        vec![0.0; archive_size]
                    } else {
                        score_deltas.iter().map(|&d| d / sum_delta).collect()
                    };

                    // pyo3 has problems with class methods, which consume references
                    // moved lehmer mean calculation function definition in local context
                    // hope, it will not slowdown common performance
                    fn calculate_weighted_lehmer_mean(values: &Vec<f64>, weights: &Vec<f64>) -> f64 {
                        let numerator: f64 = values.iter().zip(weights.iter()).map(|(v, w)| w * v * v).sum();
                        let divider: f64 = values.iter().zip(weights.iter()).map(|(v, w)| w * v).sum();

                        if divider == 0.0 {
                            0.0
                        } else {
                            numerator / divider
                        }
                    }

                    let new_cr_k = calculate_weighted_lehmer_mean(&self.history_cr, &weights);
                    self.adaptive_cr[self.k] = if new_cr_k > 0.0 { new_cr_k } else { self.initial_cr };

                    self.adaptive_mutation_proba[self.k] = 1.0 - new_cr_k;

                    let new_f_k = calculate_weighted_lehmer_mean(&self.history_f, &weights);
                    self.adaptive_f[self.k] = if new_f_k > 0.0 { new_f_k } else { self.initial_f };

                    self.k += 1;
                    if self.k >= self.current_history_archive_size {
                        self.k = 0;
                    }
                }

                // TODO: set accomplish rate like it was for Simulated Annealing.
                //self.current_history_archive_size = (self.history_archive_size as f64 + self.termination_strategy.get_accomplish_rate() *
                //    (self.minimal_history_size as f64 - self.history_archive_size as f64)).round() as usize;

                return Ok(new_population);
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
#[cfg(test)]
mod tests {
    use super::eligible_donor_indices;

    #[test]
    fn converged_population_has_no_distinct_donor_without_retrying() {
        let values = [1.0, 2.0];
        assert!(eligible_donor_indices([&values[..]; 20], &values, &values).is_empty());
    }

    #[test]
    fn donor_selection_preserves_distinct_eligible_slots() {
        let first = [1.0, 2.0];
        let current = [3.0, 4.0];
        let other = [5.0, 6.0];
        assert_eq!(
            eligible_donor_indices(
                [&first[..], &other[..], &current[..], &other[..]],
                &first,
                &current,
            ),
            vec![1, 3]
        );
    }
}
