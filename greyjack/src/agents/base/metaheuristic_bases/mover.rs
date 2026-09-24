use crate::score_calculation::score_requesters::VariablesManager;
use crate::utils::rng_utils::RngUtils;
use rustc_hash::{FxHashMap as HashMap, FxHashSet as HashSet};
use std::collections::VecDeque;

/// One repaired assignment per affected variable, shared by both scoring paths.
/// Unchanged selected values remain present so identity moves still form a sample.
#[derive(Clone, Debug, PartialEq)]
pub struct MoveDelta {
    pub ids: Vec<usize>,
    pub values: Vec<f64>,
}

impl MoveDelta {
    pub fn apply(&self, candidate: &[f64]) -> Vec<f64> {
        let mut result = candidate.to_vec();
        for (&id, &value) in self.ids.iter().zip(&self.values) {
            result[id] = value;
        }
        result
    }

    pub fn into_pairs(self) -> Vec<(usize, f64)> {
        self.ids.into_iter().zip(self.values).collect()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Operator {
    Change,
    Swap,
    SwapEdges,
    Scramble,
    Insertion,
    Inverse,
}

impl Operator {
    const ALL: [Self; 6] = [
        Self::Change,
        Self::Swap,
        Self::SwapEdges,
        Self::Scramble,
        Self::Insertion,
        Self::Inverse,
    ];

    fn minimum(self) -> usize {
        match self {
            Self::Change => 1,
            Self::Swap | Self::Insertion | Self::Inverse => 2,
            Self::SwapEdges | Self::Scramble => 3,
        }
    }
}

#[derive(Debug)]
struct EligibleOperator {
    operator: Operator,
    weight: f64,
    groups: Vec<String>,
}

#[derive(Debug)]
struct TabuHistory {
    tenure: usize,
    recent: VecDeque<usize>,
    members: HashSet<usize>,
}

#[derive(Debug)]
pub struct Mover {
    pub group_mutation_rates_map: HashMap<String, f64>,
    operators: Vec<EligibleOperator>,
    tabu: HashMap<String, TabuHistory>,
}

impl Mover {
    pub fn new(
        tabu_entity_rate: f64,
        mutation_rate_multiplier: Option<f64>,
        move_probas: Option<Vec<f64>>,
        variables_manager: &VariablesManager,
    ) -> Result<Self, String> {
        if !tabu_entity_rate.is_finite() || !(0.0..=1.0).contains(&tabu_entity_rate) {
            return Err("tabu_entity_rate must be finite and in [0, 1]".into());
        }
        let multiplier = mutation_rate_multiplier.unwrap_or(0.0);
        if !multiplier.is_finite() || multiplier < 0.0 {
            return Err("mutation_rate_multiplier must be finite and nonnegative".into());
        }
        let weights = move_probas.unwrap_or_else(|| vec![1.0 / 6.0; 6]);
        if weights.len() != 6
            || weights
                .iter()
                .any(|weight| !weight.is_finite() || *weight < 0.0)
            || (weights.iter().sum::<f64>() - 1.0).abs() > 1e-9
        {
            return Err(
                "move_probas must contain six finite nonnegative probabilities summing to 1".into(),
            );
        }
        let mut group_names: Vec<_> = variables_manager
            .semantic_groups_map
            .keys()
            .cloned()
            .collect();
        group_names.sort();
        let operators: Vec<_> = Operator::ALL
            .into_iter()
            .zip(weights)
            .filter_map(|(operator, weight)| {
                if weight == 0.0 {
                    return None;
                }
                let groups: Vec<_> = group_names
                    .iter()
                    .filter(|name| {
                        variables_manager.semantic_groups_map[*name].len() >= operator.minimum()
                    })
                    .cloned()
                    .collect();
                (!groups.is_empty()).then_some(EligibleOperator {
                    operator,
                    weight,
                    groups,
                })
            })
            .collect();
        if operators.is_empty() {
            return Err("No enabled move is eligible for the mutable semantic groups; check move_probas, group sizes, and frozen/fixed variables".into());
        }
        let mut group_mutation_rates_map = HashMap::default();
        let mut tabu = HashMap::default();
        for name in group_names {
            let count = variables_manager.semantic_groups_map[&name].len();
            if count == 0 {
                continue;
            }
            group_mutation_rates_map.insert(name.clone(), (multiplier / count as f64).min(1.0));
            tabu.insert(
                name,
                TabuHistory {
                    tenure: (tabu_entity_rate * count as f64).ceil() as usize,
                    recent: VecDeque::new(),
                    members: HashSet::default(),
                },
            );
        }
        Ok(Self {
            group_mutation_rates_map,
            operators,
            tabu,
        })
    }

    /// Select an operator first, preserving relative weights among eligible ones.
    /// Explicit zero weights were removed before sampling, including at draw zero.
    fn operator_index(&self, draw: f64) -> usize {
        let total: f64 = self.operators.iter().map(|entry| entry.weight).sum();
        let mut remaining = draw * total;
        for (index, entry) in self.operators.iter().enumerate() {
            if remaining < entry.weight {
                return index;
            }
            remaining -= entry.weight;
        }
        self.operators.len() - 1 // floating-point accumulation at the upper boundary
    }

    /// Select unique positions in a finite pass, expiring old tabu entries only
    /// when the current operator's position universe would otherwise be exhausted.
    fn select_ids(
        &mut self,
        group: &str,
        count: usize,
        right_end: usize,
    ) -> Result<Vec<usize>, String> {
        if count == 0 || count > right_end {
            return Err("Move selection exceeds its eligible position count".into());
        }
        let history = self
            .tabu
            .get_mut(group)
            .ok_or_else(|| format!("Unknown semantic group: {group}"))?;
        let mut available: Vec<_> = (0..right_end)
            .filter(|id| !history.members.contains(id))
            .collect();
        while available.len() < count {
            let oldest = history
                .recent
                .pop_back()
                .ok_or("Inconsistent tabu history")?;
            history.members.remove(&oldest);
            if oldest < right_end {
                available.push(oldest);
            }
        }
        let selected = RngUtils::choice_without_replacement(&available, count);
        if history.tenure > 0 {
            for &id in &selected {
                history.members.insert(id);
                history.recent.push_front(id);
            }
            while history.recent.len() > history.tenure {
                if let Some(oldest) = history.recent.pop_back() {
                    history.members.remove(&oldest);
                }
            }
        }
        Ok(selected)
    }

    fn change_count(&self, group: &str, capacity: usize, minimum: usize) -> usize {
        let rate = self.group_mutation_rates_map[group];
        (0..capacity)
            .filter(|_| RngUtils::random_bool(rate))
            .count()
            .max(minimum)
            .min(capacity)
    }

    pub fn sample_plain(
        &mut self,
        candidate: &[f64],
        manager: &VariablesManager,
    ) -> Result<Vec<f64>, String> {
        Ok(self.sample_delta(candidate, manager)?.apply(candidate))
    }

    pub fn sample_delta(
        &mut self,
        candidate: &[f64],
        manager: &VariablesManager,
    ) -> Result<MoveDelta, String> {
        if candidate.len() != manager.variables_count {
            return Err("Candidate length does not match the planning variables".into());
        }
        let entry = &self.operators[self.operator_index(RngUtils::get_random_f64())];
        let operator = entry.operator;
        let group = entry.groups[RngUtils::get_random_id(0, entry.groups.len())].clone();
        let ids = &manager.semantic_groups_map[&group];
        let mut delta = self.generate_delta(operator, &group, ids, candidate, manager)?;
        manager.fix_deltas(&mut delta.values, Some(delta.ids.clone()));
        Ok(delta)
    }

    fn generate_delta(
        &mut self,
        operator: Operator,
        group: &str,
        group_ids: &[usize],
        candidate: &[f64],
        manager: &VariablesManager,
    ) -> Result<MoveDelta, String> {
        let count = group_ids.len();
        match operator {
            Operator::Change | Operator::Swap => {
                let selection_size = self.change_count(group, count, operator.minimum());
                let positions = self.select_ids(group, selection_size, count)?;
                let ids: Vec<_> = positions
                    .into_iter()
                    .map(|position| group_ids[position])
                    .collect();
                let mut values: Vec<_> = if operator == Operator::Change {
                    ids.iter()
                        .map(|&id| manager.get_column_random_value(id))
                        .collect()
                } else {
                    ids.iter().map(|&id| candidate[id]).collect()
                };
                if operator == Operator::Swap {
                    values.rotate_left(1);
                }
                Ok(MoveDelta { ids, values })
            }
            Operator::SwapEdges => {
                let selection_size = self.change_count(group, count - 1, 2);
                let starts = self.select_ids(group, selection_size, count - 1)?;
                Ok(Self::edge_delta(candidate, group_ids, &starts))
            }
            Operator::Scramble => {
                let length = RngUtils::get_random_id(3, count.min(6) + 1);
                let start = self.select_ids(group, 1, count - length + 1)?[0];
                let ids = group_ids[start..start + length].to_vec();
                let mut sources = ids.clone();
                RngUtils::shuffle(&mut sources);
                let values = sources.into_iter().map(|id| candidate[id]).collect();
                Ok(MoveDelta { ids, values })
            }
            Operator::Insertion | Operator::Inverse => {
                let positions = self.select_ids(group, 2, count)?;
                let (first, second) = (positions[0], positions[1]);
                let ids = group_ids[first.min(second)..=first.max(second)].to_vec();
                let mut values: Vec<_> = ids.iter().map(|&id| candidate[id]).collect();
                if operator == Operator::Inverse {
                    values.reverse();
                } else if first < second {
                    values.rotate_left(1);
                } else {
                    values.rotate_right(1);
                }
                Ok(MoveDelta { ids, values })
            }
        }
    }

    fn edge_delta(candidate: &[f64], group_ids: &[usize], starts: &[usize]) -> MoveDelta {
        let mut ids = Vec::new();
        let mut positions = HashMap::default();
        let mut edges = Vec::new();
        for &start in starts {
            let edge = (group_ids[start], group_ids[start + 1]);
            for id in [edge.0, edge.1] {
                if !positions.contains_key(&id) {
                    positions.insert(id, ids.len());
                    ids.push(id);
                }
            }
            edges.push(edge);
        }
        let mut values: Vec<_> = ids.iter().map(|&id| candidate[id]).collect();
        edges.rotate_left(1);
        // Preserve the original plain move's sequential swaps. Overlapping edges
        // read the current scratch values, then emit each affected slot once.
        for pair in edges.windows(2) {
            values.swap(positions[&pair[0].0], positions[&pair[1].0]);
            values.swap(positions[&pair[0].1], positions[&pair[1].1]);
        }
        MoveDelta { ids, values }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::variables::GJPlanningVariable;

    fn manager(size: usize) -> VariablesManager {
        VariablesManager::new(
            (0..size)
                .map(|id| {
                    GJPlanningVariable::new(
                        id.to_string(),
                        -100.0,
                        100.0,
                        false,
                        false,
                        Some(id as f64),
                        Some(vec!["group".into()]),
                    )
                })
                .collect(),
        )
    }

    fn weights(operator: usize) -> Vec<f64> {
        let mut weights = vec![0.0; 6];
        weights[operator] = 1.0;
        weights
    }

    #[test]
    fn every_operator_has_identical_plain_and_incremental_results() {
        let manager = manager(8);
        let candidate: Vec<_> = (0..8).map(|id| id as f64).collect();
        for operator in 0..6 {
            for seed in 0..50 {
                let mut plain =
                    Mover::new(0.6, Some(4.0), Some(weights(operator)), &manager).unwrap();
                let mut incremental =
                    Mover::new(0.6, Some(4.0), Some(weights(operator)), &manager).unwrap();
                RngUtils::seed_for_tests(seed);
                let expected = plain.sample_plain(&candidate, &manager).unwrap();
                RngUtils::seed_for_tests(seed);
                let delta = incremental.sample_delta(&candidate, &manager).unwrap();
                assert!(!delta.ids.is_empty());
                assert_eq!(
                    delta.ids.len(),
                    delta.ids.iter().collect::<HashSet<_>>().len()
                );
                assert_eq!(delta.ids.len(), delta.values.len());
                let mut replay = candidate.clone();
                for (id, value) in delta.clone().into_pairs() {
                    replay[id] = value;
                }
                assert_eq!(expected, replay, "operator {operator}, seed {seed}");
                for id in 0..candidate.len() {
                    if !delta.ids.contains(&id) {
                        assert_eq!(replay[id], candidate[id]);
                    }
                }
            }
        }
    }

    #[test]
    fn edge_swaps_match_original_plain_semantics_with_and_without_overlap() {
        for (candidate, starts, expected) in [
            (vec![0., 1., 2., 3.], vec![0, 2], vec![2., 3., 0., 1.]),
            (vec![0., 1., 2.], vec![0, 1], vec![1., 2., 0.]),
            (
                vec![0., 1., 2., 3., 4., 5.],
                vec![0, 2, 4],
                vec![2., 3., 4., 5., 0., 1.],
            ),
        ] {
            let group: Vec<_> = (0..candidate.len()).collect();
            let delta = Mover::edge_delta(&candidate, &group, &starts);
            assert_eq!(delta.apply(&candidate), expected);
            assert_eq!(
                delta.ids.len(),
                delta.ids.iter().collect::<HashSet<_>>().len()
            );
        }
    }

    #[test]
    fn eligibility_covers_every_boundary_and_no_move_is_silently_enabled() {
        for size in 0..=7 {
            let manager = manager(size);
            let candidate = vec![0.; size];
            for (index, operator) in Operator::ALL.into_iter().enumerate() {
                let result = Mover::new(0.0, Some(1000.0), Some(weights(index)), &manager);
                if size < operator.minimum() {
                    assert!(result.unwrap_err().contains("No enabled move"));
                } else {
                    let mut mover = result.unwrap();
                    for _ in 0..50 {
                        let delta = mover.sample_delta(&candidate, &manager).unwrap();
                        assert!(delta.ids.len() <= size);
                        assert!(!delta.ids.is_empty());
                    }
                }
            }
        }
    }

    #[test]
    fn selection_renormalizes_positive_eligible_weights_operator_first() {
        let manager = manager(2);
        let mover =
            Mover::new(0.0, None, Some(vec![0., 0.2, 0.5, 0.2, 0.1, 0.]), &manager).unwrap();
        assert_eq!(mover.operators.len(), 2);
        assert_eq!(
            mover.operators[mover.operator_index(0.0)].operator,
            Operator::Swap
        );
        assert_eq!(
            mover.operators[mover.operator_index(0.65)].operator,
            Operator::Swap
        );
        assert_eq!(
            mover.operators[mover.operator_index(0.68)].operator,
            Operator::Insertion
        );
        assert_eq!(
            mover.operators[mover.operator_index(0.999)].operator,
            Operator::Insertion
        );
    }

    #[test]
    fn tabu_exhaustion_and_small_tenure_never_duplicate_a_batch() {
        let manager = manager(6);
        for rate in [0.0, 0.01, 0.5, 1.0] {
            let mut mover = Mover::new(rate, None, None, &manager).unwrap();
            for _ in 0..100 {
                for (count, capacity) in [(6, 6), (2, 2), (1, 1), (3, 4)] {
                    let ids = mover.select_ids("group", count, capacity).unwrap();
                    assert_eq!(ids.len(), count);
                    assert_eq!(ids.iter().collect::<HashSet<_>>().len(), count);
                    assert!(ids.iter().all(|id| *id < capacity));
                }
            }
        }
    }

    #[test]
    fn heterogeneous_groups_use_their_own_mutation_capacity() {
        RngUtils::seed_for_tests(117);
        let mut variables = manager(20).variables_vec;
        for (id, variable) in variables.iter_mut().enumerate() {
            variable.semantic_groups = vec![if id == 0 { "singleton" } else { "large" }.into()];
        }
        let manager = VariablesManager::new(variables);
        let mut mover = Mover::new(1.0, Some(1000.0), Some(weights(0)), &manager).unwrap();
        let candidate = vec![0.; 20];
        let mut saw_singleton = false;
        for _ in 0..100 {
            let delta = mover.sample_delta(&candidate, &manager).unwrap();
            if delta.ids == vec![0] {
                saw_singleton = true;
            } else {
                assert_eq!(delta.ids.len(), 19);
            }
        }
        assert!(saw_singleton);
    }

    #[test]
    fn all_operators_preserve_frozen_fixed_slots_and_repair_heterogeneous_bounds() {
        let mut variables = vec![
            GJPlanningVariable::new(
                "frozen".into(),
                0.,
                10.,
                true,
                false,
                Some(7.),
                Some(vec!["group".into()]),
            ),
            GJPlanningVariable::new(
                "fixed".into(),
                4.,
                4.,
                false,
                false,
                None,
                Some(vec!["group".into()]),
            ),
        ];
        variables.extend((2..9).map(|id| {
            GJPlanningVariable::new(
                id.to_string(),
                id as f64,
                id as f64 + 2.,
                false,
                id % 2 == 0,
                Some(id as f64),
                Some(vec!["group".into(), "group".into()]),
            )
        }));
        let mut manager = VariablesManager::new(variables);
        let candidate = manager.sample_variables();
        for operator in 0..6 {
            let mut mover = Mover::new(1.0, Some(20.0), Some(weights(operator)), &manager).unwrap();
            for seed in 0..30 {
                RngUtils::seed_for_tests(seed);
                let delta = mover.sample_delta(&candidate, &manager).unwrap();
                assert!(delta.ids.iter().all(|id| *id >= 2));
                assert_eq!(
                    delta.ids.len(),
                    delta.ids.iter().collect::<HashSet<_>>().len()
                );
                let result = delta.apply(&candidate);
                assert_eq!(&result[..2], &[7., 4.]);
                for (id, variable) in manager.variables_vec.iter().enumerate() {
                    assert!((variable.lower_bound..=variable.upper_bound).contains(&result[id]));
                    if variable.is_int {
                        assert_eq!(result[id].fract(), 0.0);
                    }
                }
            }
        }
    }

    #[test]
    fn permutation_operators_obey_their_value_transformation_contracts() {
        let manager = manager(8);
        let candidate: Vec<_> = (0..8).map(|id| id as f64).collect();
        for operator in [1, 3, 4, 5] {
            let mut mover = Mover::new(0.0, Some(4.0), Some(weights(operator)), &manager).unwrap();
            for seed in 0..30 {
                RngUtils::seed_for_tests(seed);
                let delta = mover.sample_delta(&candidate, &manager).unwrap();
                let native: Vec<_> = delta.ids.iter().map(|&id| candidate[id]).collect();
                let mut left = native.clone();
                left.rotate_left(1);
                let mut right = native.clone();
                right.rotate_right(1);
                match operator {
                    1 => assert_eq!(delta.values, left),
                    3 => {
                        let mut shuffled = delta.values.clone();
                        shuffled.sort_by(f64::total_cmp);
                        assert_eq!(shuffled, native);
                    }
                    4 => assert!(delta.values == left || delta.values == right),
                    5 => assert_eq!(delta.values, native.into_iter().rev().collect::<Vec<_>>()),
                    _ => unreachable!(),
                }
            }
        }
    }

    #[test]
    fn all_frozen_or_ungrouped_variables_have_no_eligible_portfolio() {
        let mut variables = manager(4).variables_vec;
        for variable in &mut variables {
            variable.frozen = true;
        }
        let frozen = VariablesManager::new(variables.clone());
        assert!(Mover::new(0.0, None, None, &frozen)
            .unwrap_err()
            .contains("No enabled move"));
        for variable in &mut variables {
            variable.frozen = false;
            variable.semantic_groups.clear();
        }
        let ungrouped = VariablesManager::new(variables);
        assert!(Mover::new(0.0, None, None, &ungrouped)
            .unwrap_err()
            .contains("No enabled move"));
    }

    #[test]
    fn configuration_errors_are_explicit() {
        let manager = manager(4);
        for rate in [-1.0, 1.01, f64::NAN, f64::INFINITY] {
            assert!(Mover::new(rate, None, None, &manager).is_err());
        }
        for multiplier in [-1.0, f64::NAN, f64::INFINITY] {
            assert!(Mover::new(0.0, Some(multiplier), None, &manager).is_err());
        }
        for weights in [
            vec![],
            vec![0.0; 6],
            vec![0.2; 6],
            vec![-1., 2., 0., 0., 0., 0.],
            vec![f64::NAN; 6],
            vec![f64::INFINITY; 6],
        ] {
            assert!(Mover::new(0.0, None, Some(weights), &manager).is_err());
        }
        let mut mover = Mover::new(0.0, None, None, &manager).unwrap();
        assert!(mover.sample_delta(&[], &manager).is_err());
    }
}
