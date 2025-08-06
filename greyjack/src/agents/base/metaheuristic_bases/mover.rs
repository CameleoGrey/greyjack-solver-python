use rustc_hash::FxHashMap as HashMap;
use rustc_hash::FxHashSet as HashSet;
use std::collections::VecDeque;
use crate::score_calculation::score_requesters::VariablesManager;
use crate::utils::math_utils;
use std::cmp::max;

// Import our centralized RNG utilities
use crate::utils::rng_utils::RngUtils;

pub struct Mover {
    pub tabu_entity_rate: f64,
    pub tabu_entity_size_map: HashMap<String, usize>,
    pub tabu_ids_sets_map: HashMap<String, HashSet<usize>>,
    pub tabu_ids_vecdeque_map: HashMap<String, VecDeque<usize>>,
    pub group_mutation_rates_map: HashMap<String, f64>,
    pub moves_count: u64,
    pub move_probas_thresholds: Vec<f64>,
    // REMOVED: random_generator field - using centralized RNG instead
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
        
        let move_probas_vec: Vec<f64> = match move_probas {
            None => {
                // Default uniform distribution
                let mut increments: Vec<f64> = vec![math_utils::round(1.0 / (moves_count as f64), 3); moves_count];
                increments[0] += 1.0 - increments.iter().sum::<f64>();
                
                let mut proba_thresholds = vec![0.0; moves_count];
                let mut accumulator: f64 = 0.0;
                for (i, proba) in increments.iter().enumerate() {
                    accumulator += proba;
                    proba_thresholds[i] = accumulator;
                }
                proba_thresholds
            },
            Some(probas) => {
                assert_eq!(probas.len(), moves_count, "Optional move probas vector length is not equal to available moves count");
                assert_eq!(math_utils::round(probas.iter().sum(), 1), 1.0, "Optional move probas sum must be equal to 1.0");

                let mut proba_thresholds = vec![0.0; moves_count];
                let mut accumulator: f64 = 0.0;
                for (i, proba) in probas.iter().enumerate() {
                    accumulator += proba;
                    proba_thresholds[i] = accumulator;
                }
                proba_thresholds
            }
        };

        Self {
            tabu_entity_rate,
            tabu_entity_size_map,
            tabu_ids_sets_map,
            tabu_ids_vecdeque_map,
            group_mutation_rates_map,
            moves_count: moves_count as u64,
            move_probas_thresholds: move_probas_vec,
        }
    }

    pub fn select_non_tabu_ids(&mut self, group_name: &String, selection_size: usize, right_end: usize) -> Vec<usize> {
        let mut random_ids: Vec<usize> = Vec::with_capacity(selection_size);
        
        while random_ids.len() != selection_size {
            // FIXED: Use centralized RNG instead of self.random_generator
            let random_id = RngUtils::get_random_id(0, right_end);

            if !self.tabu_ids_sets_map[group_name].contains(&random_id) {
                self.tabu_ids_sets_map.get_mut(group_name).unwrap().insert(random_id);
                self.tabu_ids_vecdeque_map.get_mut(group_name).unwrap().push_front(random_id);
                random_ids.push(random_id);

                if self.tabu_ids_vecdeque_map[group_name].len() > self.tabu_entity_size_map[group_name] {
                    let old_id = self.tabu_ids_vecdeque_map.get_mut(group_name).unwrap().pop_back().unwrap();
                    self.tabu_ids_sets_map.get_mut(group_name).unwrap().remove(&old_id);
                }
            }
        }

        random_ids
    }

    pub fn do_move(&mut self, candidate: &Vec<f64>, variables_manager: &VariablesManager, incremental: bool) 
        -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {
        
        // FIXED: Use centralized RNG instead of self.random_generator
        let random_value = RngUtils::get_random_f64();
        
        if random_value <= self.move_probas_thresholds[0] {
            self.change_move(candidate, variables_manager, incremental)
        } else if random_value <= self.move_probas_thresholds[1] {
            self.swap_move(candidate, variables_manager, incremental)
        } else if random_value <= self.move_probas_thresholds[2] {
            self.swap_edges_move(candidate, variables_manager, incremental)
        } else if random_value <= self.move_probas_thresholds[3] {
            self.scramble_move(candidate, variables_manager, incremental)
        } else if random_value <= self.move_probas_thresholds[4] {
            self.insertion_move(candidate, variables_manager, incremental)
        } else if random_value <= self.move_probas_thresholds[5] {
            self.inverse_move(candidate, variables_manager, incremental)
        } else {
            panic!("Something wrong with probabilities");
        }
    }

    fn get_necessary_info_for_move<'d>(
        &self, 
        variables_manager: &'d VariablesManager
    ) -> (&'d Vec<usize>, &'d String, usize) {
        let (group_ids, group_name) = variables_manager.get_random_semantic_group_ids();
        let group_mutation_rate = self.group_mutation_rates_map[group_name];
        
        // FIXED: Use centralized RNG for crossover mask generation
        let crossover_mask: Vec<bool> = (0..variables_manager.variables_count)
            .map(|_| RngUtils::random_bool(group_mutation_rate))
            .collect();
        
        let current_change_count = crossover_mask.iter().filter(|&&x| x).count();
        (group_ids, group_name, current_change_count)
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

        let changed_columns: Vec<usize> = if self.tabu_entity_rate == 0.0 {
            math_utils::choice(&(0..group_ids.len()).collect::<Vec<usize>>(), current_change_count, false)
        } else {
            self.select_non_tabu_ids(group_name, current_change_count, group_ids.len())
        };
        
        let changed_columns: Vec<usize> = changed_columns.iter().map(|&i| group_ids[i]).collect();

        if incremental {
            let deltas: Vec<f64> = changed_columns.iter()
                .map(|&i| variables_manager.get_column_random_value(i))
                .collect();
            (None, Some(changed_columns), Some(deltas))
        } else {
            let mut changed_candidate = candidate.clone();
            for &i in &changed_columns {
                changed_candidate[i] = variables_manager.get_column_random_value(i);
            }
            (Some(changed_candidate), Some(changed_columns), None)
        }
    }

    pub fn swap_move(
        &mut self, 
        candidate: &Vec<f64>, 
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

        let changed_columns: Vec<usize> = if self.tabu_entity_rate == 0.0 {
            math_utils::choice(&(0..group_ids.len()).collect::<Vec<usize>>(), current_change_count, false)
        } else {
            self.select_non_tabu_ids(group_name, current_change_count, group_ids.len())
        };
        
        let changed_columns: Vec<usize> = changed_columns.iter().map(|&i| group_ids[i]).collect();

        if incremental {
            let mut deltas: Vec<f64> = Vec::with_capacity(current_change_count);
            for i in 0..current_change_count {
                deltas.push(candidate[changed_columns[i]]);
            }
            // Apply swap pattern - rotate values
            for i in 1..current_change_count {
                deltas.swap(i-1, i);
            }
            (None, Some(changed_columns), Some(deltas))
        } else {
            let mut changed_candidate = candidate.clone();
            for i in 1..current_change_count {
                changed_candidate.swap(changed_columns[i-1], changed_columns[i]);
            }
            (Some(changed_candidate), Some(changed_columns), None)
        }
    }

    pub fn swap_edges_move(
        &mut self, 
        candidate: &Vec<f64>, 
        variables_manager: &VariablesManager, 
        incremental: bool,
    ) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {
        let (group_ids, group_name, mut current_change_count) = self.get_necessary_info_for_move(variables_manager);

        if group_ids.is_empty() {
            return (None, None, None);
        }
        if current_change_count < 2 {
            current_change_count = 2;
        }
        if current_change_count > group_ids.len() - 1 {
            current_change_count = group_ids.len() - 1;
        }

        let columns_to_change: Vec<usize> = if self.tabu_entity_rate == 0.0 {
            math_utils::choice(&(0..(group_ids.len()-1)).collect::<Vec<usize>>(), current_change_count, false)
        } else {
            self.select_non_tabu_ids(group_name, current_change_count, group_ids.len()-1)
        };

        let mut edges: Vec<(usize, usize)> = Vec::with_capacity(current_change_count);
        let mut changed_columns: Vec<usize> = Vec::with_capacity(current_change_count * 2);
        
        for i in 0..current_change_count {
            let edge = (group_ids[columns_to_change[i]], group_ids[columns_to_change[i] + 1]);
            edges.push(edge);
            changed_columns.push(edge.0);
            changed_columns.push(edge.1);
        }
        
        edges.rotate_left(1);

        if incremental {
            let mut deltas: Vec<f64> = Vec::with_capacity(changed_columns.len());
            for edge in &edges {
                deltas.push(candidate[edge.0]);
                deltas.push(candidate[edge.1]);
            }
            
            // Apply edge swap pattern
            for i in 1..current_change_count {
                deltas.swap(2*(i-1), 2*i);
                deltas.swap(2*(i-1) + 1, 2*i + 1);
            }
            
            (None, Some(changed_columns), Some(deltas))
        } else {
            let mut changed_candidate = candidate.clone();
            for i in 1..current_change_count {
                let left_edge = edges[i-1];
                let right_edge = edges[i];
                changed_candidate.swap(left_edge.0, right_edge.0);
                changed_candidate.swap(left_edge.1, right_edge.1);
            }
            (Some(changed_candidate), Some(changed_columns), None)
        }
    }

    pub fn scramble_move(
        &mut self, 
        candidate: &Vec<f64>, 
        variables_manager: &VariablesManager, 
        incremental: bool,
    ) -> (Option<Vec<f64>>, Option<Vec<usize>>, Option<Vec<f64>>) {
        // FIXED: Use centralized RNG for range generation
        let current_change_count = RngUtils::get_random_id(3, 7); // 3 to 6 inclusive
        let (group_ids, group_name) = variables_manager.get_random_semantic_group_ids();

        if group_ids.len() < current_change_count {
            return (None, None, None);
        }

        let current_start_id: usize = if self.tabu_entity_rate == 0.0 {
            RngUtils::get_random_id(0, group_ids.len() - current_change_count + 1)
        } else {
            let selected = self.select_non_tabu_ids(group_name, 1, group_ids.len() - current_change_count + 1);
            selected[0]
        };

        let native_columns: Vec<usize> = (0..current_change_count)
            .map(|i| group_ids[current_start_id + i])
            .collect();
        
        let mut scrambled_columns = native_columns.clone();
        // FIXED: Use centralized RNG for shuffling
        RngUtils::shuffle(&mut scrambled_columns);

        if incremental {
            let deltas: Vec<f64> = scrambled_columns.iter()
                .map(|&i| candidate[i])
                .collect();
            (None, Some(native_columns), Some(deltas))
        } else {
            let mut changed_candidate = candidate.clone();
            for (&original, &scrambled) in native_columns.iter().zip(scrambled_columns.iter()) {
                changed_candidate[original] = candidate[scrambled];
            }
            (Some(changed_candidate), Some(native_columns), None)
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

        let columns_to_change: Vec<usize> = if self.tabu_entity_rate == 0.0 {
            math_utils::choice(&(0..group_ids.len()).collect::<Vec<usize>>(), current_change_count, false)
        } else {
            self.select_non_tabu_ids(group_name, current_change_count, group_ids.len())
        };

        let get_out_id = columns_to_change[0];
        let put_in_id = columns_to_change[1];
        
        let (old_ids, left_rotate) = if get_out_id < put_in_id {
            (
                (get_out_id..=put_in_id).map(|i| group_ids[i]).collect::<Vec<usize>>(),
                true
            )
        } else if get_out_id > put_in_id {
            (
                (put_in_id..=get_out_id).map(|i| group_ids[i]).collect::<Vec<usize>>(),
                false
            )
        } else {
            return (None, None, None);
        };

        let changed_columns = old_ids.clone();

        if incremental {
            let mut deltas: Vec<f64> = old_ids.iter().map(|&old_id| candidate[old_id]).collect();
            if left_rotate {
                deltas.rotate_left(1);
            } else {
                deltas.rotate_right(1);
            }
            (None, Some(changed_columns), Some(deltas))
        } else {
            let mut changed_candidate = candidate.clone();
            let values: Vec<f64> = old_ids.iter().map(|&id| candidate[id]).collect();
            let rotated_values = if left_rotate {
                let mut v = values;
                v.rotate_left(1);
                v
            } else {
                let mut v = values;
                v.rotate_right(1);
                v
            };
            
            for (&old_id, &new_value) in old_ids.iter().zip(rotated_values.iter()) {
                changed_candidate[old_id] = new_value;
            }
            (Some(changed_candidate), Some(changed_columns), None)
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

        let columns_to_change: Vec<usize> = if self.tabu_entity_rate == 0.0 {
            math_utils::choice(&(0..group_ids.len()).collect::<Vec<usize>>(), current_change_count, false)
        } else {
            self.select_non_tabu_ids(group_name, current_change_count, group_ids.len())
        };

        let mut ids_to_change = vec![columns_to_change[0], columns_to_change[1]];
        if ids_to_change[1] < ids_to_change[0] {
            ids_to_change.swap(0, 1);
        }
        let get_out_id = ids_to_change[0];
        let put_in_id = ids_to_change[1];

        let old_ids: Vec<usize> = (get_out_id..=put_in_id)
            .map(|i| group_ids[i])
            .collect();

        let changed_columns = old_ids.clone();
        
        if incremental {
            let mut deltas: Vec<f64> = old_ids.iter().map(|&rev_id| candidate[rev_id]).collect();
            deltas.reverse();
            (None, Some(changed_columns), Some(deltas))
        } else {
            let mut changed_candidate = candidate.clone();
            let changed_values: Vec<f64> = old_ids.iter().rev().map(|&i| candidate[i]).collect();
            for (&old_id, &new_value) in old_ids.iter().zip(changed_values.iter()) {
                changed_candidate[old_id] = new_value;
            }
            (Some(changed_candidate), Some(changed_columns), None)
        }
    }
}
