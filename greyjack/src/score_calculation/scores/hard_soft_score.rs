
use pyo3::prelude::*;
use crate::utils::math_utils::round;
use std::cmp::Ordering;
use std::cmp::Ordering::*;
use std::ops::{Add, AddAssign};
use std::fmt::{Display, Formatter};

#[pyclass(str, eq, ord)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct HardSoftScore {
    pub hard_score: f64,
    pub soft_score: f64
}

#[pymethods]
impl HardSoftScore {

    #[new]
    #[pyo3(signature = (hard_score, soft_score))]
    pub fn new(hard_score: f64, soft_score: f64) -> Self{
        HardSoftScore{
            hard_score: hard_score,
            soft_score: soft_score
        }
    }

    #[getter]
    pub fn get_hard_score(&self) -> f64 {
        self.hard_score
    }

    #[getter]
    pub fn get_soft_score(&self) -> f64 {
        self.soft_score
    }

    #[setter]
    pub fn set_hard_score(&mut self, value: f64) {
        self.hard_score = value;
    }

    #[setter]
    pub fn set_soft_score(&mut self, value: f64) {
        self.soft_score = value;
    }

    pub fn get_sum_abs(&self) -> f64 {
        self.hard_score.abs() + self.soft_score.abs()
    }

    pub fn get_priority_score(&self) -> f64 {
        if self.hard_score > 0.0 {
            return self.hard_score;
        } else {
            return self.soft_score;
        }
    }

    pub fn get_fitness_value(&self) -> f64 {
        let hard_fitness = 1.0 - (1.0 / (self.hard_score + 1.0));
        let soft_fitness = 1.0 - (1.0 / (self.soft_score + 1.0));
        let fitness_value = 0.5 * hard_fitness + 0.5 * soft_fitness;
        
        return fitness_value;
    }

    #[staticmethod]
    pub fn get_null_score() -> Self {
        HardSoftScore {
            hard_score: 0.0,
            soft_score: 0.0
        }
    }

    #[staticmethod]
    pub fn get_stub_score() -> Self {
        HardSoftScore {
            hard_score: f64::MAX - 1.0,
            soft_score: f64::MAX - 1.0
        }
    }

    pub fn mul(&self, scalar: f64) -> Self {
        HardSoftScore {
            hard_score: scalar * self.hard_score,
            soft_score: scalar * self.soft_score
        }
    }

    #[staticmethod]
    pub fn precision_len() -> usize {
        2
    }

    pub fn round(&mut self, precision: Vec<u64>) {
        self.hard_score = round(self.hard_score, precision[0]);
        self.soft_score = round(self.soft_score, precision[1]);
    }

    pub fn __add__(&self, rhs: &Self) -> Self {
        Self {
            hard_score: self.hard_score + rhs.hard_score,
            soft_score: self.soft_score + rhs.soft_score,
        }
    }
    
    pub fn __repr__(&self) -> String {
        return self.hard_score.to_string() + " | " + &self.soft_score.to_string();
    }

    pub fn as_list(&self) -> Vec<f64> {
        vec![self.hard_score, self.soft_score]
    }

    #[staticmethod]
    pub fn from_list(score_list: Vec<f64>) -> Self {
        Self {
            hard_score: score_list[0],
            soft_score: score_list[1]
        }
    }
}

impl Eq for HardSoftScore {}

impl Ord for HardSoftScore {

    fn cmp(&self, other: &Self) -> Ordering {
        let hard_score_ordering = self.hard_score.total_cmp(&other.hard_score);

        match hard_score_ordering {
            Less => return hard_score_ordering,
            Greater => return hard_score_ordering,
            Equal => return self.soft_score.total_cmp(&other.soft_score)
        }
    }
    
}

impl Add for HardSoftScore {
    type Output = Self;

    fn add(self, rhs: Self) -> Self::Output {
        HardSoftScore {
            hard_score: self.hard_score + rhs.hard_score,
            soft_score: self.soft_score + rhs.soft_score,
        }
    }
}

impl AddAssign for HardSoftScore {
    fn add_assign(&mut self, rhs: Self) {
        self.hard_score += rhs.hard_score;
        self.soft_score += rhs.soft_score;
    }
}

impl Display for HardSoftScore {

    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} | {}", self.hard_score, self.soft_score)
    }
    
}

unsafe impl Send for HardSoftScore {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hard_soft_score_impl() {
        let score = HardSoftScore::new(-1.0, -1.0);
        assert_eq!(score.get_sum_abs(), 2.0);

        let score = HardSoftScore::new(0.0, 9.0);
        assert_eq!(score.get_priority_score(), 9.0);
        assert_eq!(score.get_fitness_value(), 0.45);
    }

    #[test]
    fn test_hard_soft_score_comparison() {

        let small_score = HardSoftScore::new(-1.0, -1.0);
        let null_score = HardSoftScore::new(0.0, 0.0);
        let large_score = HardSoftScore::new(0.0, 0.1);

        assert_eq!(small_score < large_score, true);
        assert_eq!(small_score <= large_score, true);
        assert_eq!(small_score != large_score, true);
        assert_eq!(null_score == null_score, true);
        assert_eq!(large_score > null_score, true);
        assert_eq!(large_score >= large_score, true);
        
        let mut scores_vec_1: Vec<HardSoftScore> = Vec::new();
        for i in 0..10 {
            scores_vec_1.push(HardSoftScore::new(i as f64, (2 * i) as f64));
        }
        let scores_vec_2 = scores_vec_1.clone();
        scores_vec_1.reverse();
        scores_vec_1.sort();
        assert_eq!(scores_vec_1, scores_vec_2);

        let mut scores_vec_1: Vec<HardSoftScore> = Vec::new();
        for i in 0..10 {
            scores_vec_1.push(HardSoftScore::new(0 as f64, i as f64));
        }
        let scores_vec_2 = scores_vec_1.clone();
        scores_vec_1.reverse();
        scores_vec_1.sort();
        assert_eq!(scores_vec_1, scores_vec_2);
        
    }

    #[test]
    fn test_simple_score_add() {
        let mut score_1 = HardSoftScore::new(-1.0, -1.0);
        let score_2 = HardSoftScore::new(1.0, 1.0);
        let score_3 = HardSoftScore::new(0.0, 0.0);
        assert_eq!(score_1.clone() + score_2.clone(), score_3);

        score_1 += score_2.clone();
        assert_eq!(score_1, score_3);
    }
}