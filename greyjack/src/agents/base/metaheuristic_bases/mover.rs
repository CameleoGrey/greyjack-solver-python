
use std::collections::HashMap;
use std::collections::HashSet;
use std::collections::VecDeque;
use crate::score_calculation::score_requesters::VariablesManager;
use crate::utils;
use rand::{seq::SliceRandom, SeedableRng};
use rand::rngs::StdRng;
use rand_distr::{Distribution, Uniform};
use crate::utils::math_utils;

pub struct Mover {

    pub tabu_entity_rate: f64,
    pub tabu_entity_size_map: HashMap<String, usize>,
    pub tabu_ids_sets_map: HashMap<String, HashSet<usize>>,
    pub tabu_ids_vecdeque_map: HashMap<String, VecDeque<usize>>,
    pub group_mutation_rates_map: HashMap<String, f64>,
    pub moves_count: u64,
    pub move_probas_tresholds: Vec<f64>,

}

impl Mover {

    pub fn new(
        tabu_entity_rate: f64,
        tabu_entity_size_map: HashMap<String, usize>,
        tabu_ids_sets_map: HashMap<String, HashSet<usize>>,
        tabu_ids_vecdeque_map: HashMap<String, VecDeque<usize>>,
        group_mutation_rates_map: HashMap<String, f64>,
        move_probas: Option<Vec<f64>>,
        
    ) -> Self {

        let moves_count = 6;
        let move_probas_vec: Vec<f64>;
        match move_probas {
            None => {
                let mut increments: Vec<f64> = vec![math_utils::round(1.0 / (moves_count as f64), 3); moves_count];
                increments[0] += 1.0 - increments.iter().sum::<f64>();
                let mut proba_tresholds = vec![0.0; moves_count];
                let mut accumulator: f64 = 0.0;
                increments.iter().enumerate().for_each(|(i, proba)| {
                    accumulator += proba;
                    proba_tresholds[i] = accumulator;
                });
                move_probas_vec = proba_tresholds;
            },
            Some(probas) => {
                assert_eq!(probas.len(), moves_count, "Optional move probas vector length is not equal to available moves count");
                assert_eq!(utils::math_utils::round(probas.iter().sum(), 1), 1.0, "Optional move probas sum must be equal to 1.0");

                let mut proba_tresholds = vec![0.0; moves_count];
                let mut accumulator: f64 = 0.0;
                probas.iter().enumerate().for_each(|(i, proba)| {
                    accumulator += proba;
                    proba_tresholds[i] = accumulator;
                });
                move_probas_vec = proba_tresholds;
            }
        }

        Self {
            tabu_entity_rate: tabu_entity_rate,
            tabu_entity_size_map: tabu_entity_size_map,
            tabu_ids_sets_map: tabu_ids_sets_map,
            tabu_ids_vecdeque_map: tabu_ids_vecdeque_map,
            group_mutation_rates_map: group_mutation_rates_map,
            moves_count: moves_count as u64,
            move_probas_tresholds: move_probas_vec,
        }
    }

    pub fn select_non_tabu_ids(&mut self, group_name: &String, selection_size: usize, right_end: usize) -> Vec<usize> {

        let mut random_ids: Vec<usize> = Vec::new();
        while random_ids.len() != selection_size {
            let random_id = math_utils::get_random_id(0, right_end);

            if self.tabu_ids_sets_map[group_name].contains(&random_id) == false {
                self.tabu_ids_sets_map.get_mut(group_name).unwrap().insert(random_id);
                self.tabu_ids_vecdeque_map.get_mut(group_name).unwrap().push_front(random_id);
                random_ids.push(random_id);

                if self.tabu_ids_vecdeque_map[group_name].len() > self.tabu_entity_size_map[group_name] {
                    self.tabu_ids_sets_map.get_mut(group_name).unwrap().remove( 
                        &self.tabu_ids_vecdeque_map.get_mut(group_name).unwrap().pop_back().unwrap()
                    );
                }
            }

        }

        return random_ids;
    }

    pub fn do_move(&mut self, candidate: &Vec<f64>, variables_manager: &VariablesManager, incremental: bool) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {

        let changed_candidate: Option<Vec<f64>>;
        let changed_columns: Option<Vec<usize>>;
        let deltas: Option<Vec<f64>>;

        let random_value = Uniform::new_inclusive(0.0, 1.0).sample(&mut StdRng::from_entropy());
        if random_value <= self.move_probas_tresholds[0] {
            (changed_candidate, changed_columns, deltas) = self.change_move(candidate, variables_manager, incremental);

        } else if random_value <= self.move_probas_tresholds[1] {
            (changed_candidate, changed_columns, deltas) = self.swap_move(candidate, variables_manager, incremental)

        } else if random_value <= self.move_probas_tresholds[2] {
            (changed_candidate, changed_columns, deltas) = self.swap_edges_move(candidate, variables_manager, incremental)

        } else if random_value <= self.move_probas_tresholds[3] {
            (changed_candidate, changed_columns, deltas) = self.scramble_move(candidate, variables_manager, incremental)

        } else if random_value <= self.move_probas_tresholds[4] {
            (changed_candidate, changed_columns, deltas) = self.insertion_move(candidate, variables_manager, incremental)

        } else if random_value <= self.move_probas_tresholds[5] {
            (changed_candidate, changed_columns, deltas) = self.inverse_move(candidate, variables_manager, incremental)

        } else {
            panic!("Something wrong with probabilities");
        }

        return (changed_candidate, changed_columns, deltas);
    }

    fn get_necessary_info_for_move<'d>(
        &self, 
        variables_manager: &'d VariablesManager
    ) -> (&'d Vec<usize>, &'d String, usize) {
    
        let (group_ids, group_name) = variables_manager.get_random_semantic_group_ids();
        let group_mutation_rate = self.group_mutation_rates_map[group_name];
        let mut random_generator = StdRng::from_entropy();
        let random_values: Vec<f64> = (0..variables_manager.variables_count).into_iter().map(|x| Uniform::new_inclusive(0.0, 1.0).sample(&mut random_generator)).collect();
        let crossover_mask: Vec<bool> = random_values.iter().map(|x| x < &group_mutation_rate).collect();
        let current_change_count = crossover_mask.iter().filter(|x| **x == true).count();

        return (group_ids, group_name, current_change_count);
    }

    pub fn change_move(
        &mut self, 
        candidate: &Vec<f64>, 
        variables_manager: &VariablesManager,
        incremental: bool,
    ) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {
        
        let (group_ids, group_name, mut current_change_count) = self.get_necessary_info_for_move(variables_manager);

        if current_change_count < 1 {
            current_change_count = 1;
        }
        if group_ids.len() < current_change_count {
            return (None, None, None);
        }

        let mut changed_columns: Vec<usize>;
        if self.tabu_entity_rate == 0.0 {
            changed_columns = math_utils::choice(&(0..group_ids.len()).collect::<Vec<usize>>(), current_change_count, false);
        } else {
            changed_columns = self.select_non_tabu_ids(group_name, current_change_count, group_ids.len());
        }
        changed_columns = changed_columns.iter().map(|i| group_ids[*i]).collect();

        if incremental {
            let deltas: Vec<f64> = changed_columns.iter().map(|i| variables_manager.get_column_random_value(*i)).collect();
            return (None, Some(changed_columns), Some(deltas));
        } else {
            let mut changed_candidate = candidate.clone();
            changed_columns.iter().for_each(|i| changed_candidate[*i] = variables_manager.get_column_random_value(*i));
            return (Some(changed_candidate), Some(changed_columns), None);
        }
    }

    pub fn swap_move(
        &mut self, candidate: 
        &Vec<f64>, 
        variables_manager: &VariablesManager, 
        incremental: bool,
    ) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {

        let (group_ids, group_name, mut current_change_count) = self.get_necessary_info_for_move(variables_manager);

        if current_change_count < 2 {
            current_change_count = 2;
        }
        if group_ids.len() < current_change_count {
            return (None, None, None);
        }

        let mut changed_columns: Vec<usize>;
        if self.tabu_entity_rate == 0.0 {
            changed_columns = math_utils::choice(&(0..group_ids.len()).collect::<Vec<usize>>(), current_change_count, false);
        } else {
            changed_columns = self.select_non_tabu_ids(group_name, current_change_count, group_ids.len());
        }
        changed_columns = changed_columns.iter().map(|i| group_ids[*i]).collect();

        if incremental {
            let mut deltas: Vec<f64> = Vec::new();
            (0..current_change_count).into_iter().for_each(|i| deltas.push(candidate[changed_columns[i]]));
            (1..current_change_count).into_iter().for_each(|i| deltas.swap(i-1, i));

            return (None, Some(changed_columns), Some(deltas));
        } else {
            let mut changed_candidate = candidate.clone();
            for i in 1..current_change_count {
                changed_candidate.swap(changed_columns[i-1], changed_columns[i]);
            }
            return (Some(changed_candidate), Some(changed_columns), None);
        }
    }

    pub fn swap_edges_move(
        &mut self, 
        candidate: &Vec<f64>, 
        variables_manager: &VariablesManager, 
        incremental: bool,
    ) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {

        let (group_ids, group_name, mut current_change_count) = self.get_necessary_info_for_move(variables_manager);

        if group_ids.len() == 0 {
            return (None, None, None);
        }
        if current_change_count < 2 {
            current_change_count = 2;
        }
        if current_change_count > group_ids.len()-1 {
            current_change_count = group_ids.len()-1;
        }

        let columns_to_change: Vec<usize>;
        if self.tabu_entity_rate == 0.0 {
            columns_to_change = math_utils::choice(&(0..(group_ids.len()-1)).collect(), current_change_count, false);
        } else {
            columns_to_change = self.select_non_tabu_ids(group_name, current_change_count, group_ids.len()-1);
        }

        let mut edges: Vec<(usize, usize)> = Vec::new();
        let mut changed_columns: Vec<usize> = Vec::new();
        for i in 0..current_change_count {
            let edge = (group_ids[columns_to_change[i]], group_ids[columns_to_change[i] + 1]);
            edges.push(edge);
            changed_columns.push(edge.0);
            changed_columns.push(edge.1);
        }
        edges.rotate_left(1);

        if incremental {
            let mut deltas: Vec<f64> = Vec::new();

            (edges).iter().for_each(|edge| {
                deltas.push(candidate[edge.0]);
                deltas.push(candidate[edge.1]);
            });

            (1..current_change_count).into_iter().for_each(|i| {
                deltas.swap(2*(i-1), 2*i);
                deltas.swap(2*(i-1) + 1, 2*i + 1);
            });

            return (None, Some(changed_columns), Some(deltas));
        } else {
            let mut changed_candidate = candidate.clone();
            for i in 1..current_change_count {
                let left_edge = edges[i-1];
                let right_edge = edges[i];
                changed_candidate.swap(left_edge.0, right_edge.0);
                changed_candidate.swap(left_edge.1, right_edge.1);
            }
            return (Some(changed_candidate), Some(changed_columns), None);
        }
    }

    pub fn scramble_move(
        &mut self, 
        candidate: &Vec<f64>, 
        variables_manager: &VariablesManager, 
        incremental: bool,
    ) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {

        let current_change_count = Uniform::new_inclusive(3, 6).sample(&mut StdRng::from_entropy());
        let (group_ids, group_name) = variables_manager.get_random_semantic_group_ids();

        if group_ids.len() < current_change_count - 1 {
            return (None, None, None);
        }

        let current_start_id: usize;
        if self.tabu_entity_rate == 0.0 {
            current_start_id = math_utils::get_random_id(0, group_ids.len() - current_change_count);
        } else {
            current_start_id = self.select_non_tabu_ids(group_name, 1, group_ids.len() - current_change_count)[0];
        }

        let native_columns: Vec<usize> = (0..current_change_count).into_iter().map(|i| group_ids[current_start_id + i]).collect();
        let mut scrambled_columns = native_columns.clone();
        scrambled_columns.shuffle(&mut StdRng::from_entropy());


        if incremental {
            let mut deltas: Vec<f64> = Vec::new();
            scrambled_columns.iter().for_each(|i| deltas.push(candidate[*i]));
            return (None, Some(scrambled_columns), Some(deltas));
        } else {
            let changed_columns = native_columns.clone();
            let mut changed_candidate = candidate.clone();
            native_columns.iter().zip(scrambled_columns.iter()).for_each(|(oi, si)| changed_candidate.swap(*oi, *si));
            return (Some(changed_candidate), Some(changed_columns), None);
        }
    }

    pub fn insertion_move(
        &mut self, 
        candidate: &Vec<f64>, 
        variables_manager: &VariablesManager, 
        incremental: bool,
    ) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {

        let (group_ids, group_name) = variables_manager.get_random_semantic_group_ids();
        let current_change_count = 2;

        if group_ids.len() <= 1 {
            return (None, None, None);
        }

        let columns_to_change: Vec<usize>;
        if self.tabu_entity_rate == 0.0 {
            columns_to_change = math_utils::choice(&(0..group_ids.len()).collect::<Vec<usize>>(), current_change_count, false);
        } else {
            columns_to_change = self.select_non_tabu_ids(group_name, current_change_count, group_ids.len());
        }

        let get_out_id = columns_to_change[0];
        let put_in_id = columns_to_change[1];
        let old_ids: Vec<usize>;
        let mut shifted_ids: Vec<usize>;
        let left_rotate;
        if get_out_id < put_in_id {
            old_ids = (get_out_id..=put_in_id).into_iter().map(|i| group_ids[i]).collect();
            shifted_ids = old_ids.clone();
            shifted_ids.rotate_left(1);
            left_rotate = true;

        } else if get_out_id > put_in_id {
            old_ids = (put_in_id..=get_out_id).into_iter().map(|i| group_ids[i]).collect();
            shifted_ids = old_ids.clone();
            shifted_ids.rotate_right(1);
            left_rotate = false;

        } else {
            return (None, None, None);
        }

        let changed_columns = old_ids.clone();

        if incremental {
            let mut deltas: Vec<f64> = old_ids.iter().map(|old_id| candidate[*old_id]).collect();
            if left_rotate {
                deltas.rotate_left(1);
            } else {
                deltas.rotate_right(1);
            }
            return (None, Some(changed_columns), Some(deltas));
        } else {
            let mut changed_candidate = candidate.clone();
            old_ids.iter().zip(shifted_ids.iter()).for_each(|(oi, si)| changed_candidate.swap(*oi, *si));
            return (Some(changed_candidate), Some(changed_columns), None);
        }
    }

    pub fn inverse_move(
        &mut self, 
        candidate: &Vec<f64>, 
        variables_manager: &VariablesManager, 
        incremental: bool,
    ) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {

        let (group_ids, group_name) = variables_manager.get_random_semantic_group_ids();
        let current_change_count = 2;

        if group_ids.len() <= 1 {
            return (None, None, None);
        }

        let columns_to_change: Vec<usize>;
        if self.tabu_entity_rate == 0.0 {
            columns_to_change = math_utils::choice(&(0..group_ids.len()).collect::<Vec<usize>>(), current_change_count, false);
        } else {
            columns_to_change = self.select_non_tabu_ids(group_name, current_change_count, group_ids.len());
        }

        let mut ids_to_change = vec![columns_to_change[0], columns_to_change[1]];
        if ids_to_change[1] < ids_to_change[0] {
            ids_to_change.swap(0, 1);
        }
        let get_out_id = ids_to_change[0];
        let put_in_id = ids_to_change[1];

        let old_ids: Vec<usize>;
        let mut reversed_ids: Vec<usize>;
        old_ids = (get_out_id..=put_in_id).into_iter().map(|i| group_ids[i]).collect();
        reversed_ids = old_ids.clone();
        reversed_ids.reverse();

        let changed_columns = old_ids.clone();
        if incremental {
            let deltas: Vec<f64> = reversed_ids.iter().map(|rev_id| candidate[*rev_id]).collect();
            return (None, Some(changed_columns), Some(deltas));
        } else {
            let mut changed_candidate = candidate.clone();
            let changed_values: Vec<f64> = reversed_ids.iter().map(|i| candidate[*i]).collect();
            old_ids.iter().zip(changed_values.iter()).for_each(|(oi, new_value)| changed_candidate[*oi] = *new_value);
            return (Some(changed_candidate), Some(changed_columns), None);
        }
    }
}