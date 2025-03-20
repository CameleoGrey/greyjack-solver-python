

use pyo3::prelude::*;
use crate::utils::math_utils::round;
use std::cmp::Ordering;
use std::cmp::Ordering::*;
use std::ops::{Add, AddAssign};
use std::fmt::{Display, Formatter};

#[pyclass(str, eq, ord)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct HardMediumSoftScore {
    pub hard_score: f64,
    pub medium_score: f64,
    pub soft_score: f64
}

#[pymethods]
impl HardMediumSoftScore {

    #[new]
    #[pyo3(signature = (hard_score, medium_score, soft_score))]
    pub fn new(hard_score: f64, medium_score: f64, soft_score: f64) -> Self{
        HardMediumSoftScore{
            hard_score: hard_score,
            medium_score: medium_score,
            soft_score: soft_score
        }
    }

    #[getter]
    pub fn get_hard_score(&self) -> f64 {
        self.hard_score
    }

    #[getter]
    pub fn get_medium_score(&self) -> f64 {
        self.medium_score
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
    pub fn set_medium_score(&mut self, value: f64) {
        self.medium_score = value;
    }

    #[setter]
    pub fn set_soft_score(&mut self, value: f64) {
        self.soft_score = value;
    }

    pub fn get_sum_abs(&self) -> f64 {
        self.hard_score.abs() + self.medium_score.abs() + self.soft_score.abs()
    }

    pub fn get_priority_score(&self) -> f64 {
        if self.hard_score > 0.0 {
            return self.hard_score;
        } else if self.medium_score > 0.0{
            return self.medium_score;
        } else {
            return self.soft_score;
        }
    }

    pub fn get_fitness_value(&self) -> f64 {
        let hard_fitness = 1.0 - (1.0 / (self.hard_score + 1.0));
        let medium_fitness = 1.0 - (1.0 / (self.medium_score + 1.0));
        let soft_fitness = 1.0 - (1.0 / (self.soft_score + 1.0));
        let fitness_value = 0.33 * hard_fitness + 0.33 * medium_fitness + 0.33 * soft_fitness;
        
        return fitness_value;
    }

    #[staticmethod]
    pub fn get_null_score() -> Self {
        HardMediumSoftScore {
            hard_score: 0.0,
            medium_score: 0.0,
            soft_score: 0.0
        }
    }

    #[staticmethod]
    pub fn get_stub_score() -> Self {
        HardMediumSoftScore {
            hard_score: f64::MAX - 1.0,
            medium_score: f64::MAX - 1.0,
            soft_score: f64::MAX - 1.0
        }
    }

    pub fn mul(&self, scalar: f64) -> Self {
        HardMediumSoftScore {
            hard_score: scalar * self.hard_score,
            medium_score: scalar * self.medium_score,
            soft_score: scalar * self.soft_score
        }
    }

    #[staticmethod]
    pub fn precision_len() -> usize {
        3
    }

    pub fn round(&mut self, precision: Vec<u64>) {
        self.hard_score = round(self.hard_score, precision[0]);
        self.medium_score = round(self.medium_score, precision[1]);
        self.soft_score = round(self.soft_score, precision[2]);
    }

    pub fn __add__(&self, rhs: &Self) -> Self {
        Self {
            hard_score: self.hard_score + rhs.hard_score,
            medium_score: self.medium_score + rhs.medium_score,
            soft_score: self.soft_score + rhs.soft_score,
        }
    }
    
    pub fn __repr__(&self) -> String {
        return self.hard_score.to_string() + " | " + &self.medium_score.to_string() + " | " + &self.soft_score.to_string();
    }

    pub fn as_list(&self) -> Vec<f64> {
        vec![self.hard_score, self.medium_score, self.soft_score]
    }

    #[staticmethod]
    pub fn from_list(score_list: Vec<f64>) -> Self {
        Self {
            hard_score: score_list[0],
            medium_score: score_list[1],
            soft_score: score_list[2]
        }
    }
}

impl Eq for HardMediumSoftScore {}

impl Ord for HardMediumSoftScore {

    fn cmp(&self, other: &Self) -> Ordering {

        let hard_score_ordering = self.hard_score.total_cmp(&other.hard_score);
        match hard_score_ordering {
            Less => return hard_score_ordering,
            Greater => return hard_score_ordering,
            Equal => {

                let medium_score_ordering = self.medium_score.total_cmp(&other.medium_score);
                match medium_score_ordering {
                    Less => return medium_score_ordering,
                    Greater => return medium_score_ordering,
                    Equal => self.soft_score.total_cmp(&other.soft_score)
                }
            }
        }
    }
    
}

impl Add for HardMediumSoftScore {
    type Output = Self;

    fn add(self, rhs: Self) -> Self::Output {
        HardMediumSoftScore {
            hard_score: self.hard_score + rhs.hard_score,
            medium_score: self.medium_score + rhs.medium_score,
            soft_score: self.soft_score + rhs.soft_score,
        }
    }
}

impl AddAssign for HardMediumSoftScore {
    fn add_assign(&mut self, rhs: Self) {
        self.hard_score += rhs.hard_score;
        self.medium_score += rhs.medium_score;
        self.soft_score += rhs.soft_score;
    }
}

impl Display for HardMediumSoftScore {

    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} | {} | {}", self.hard_score, self.medium_score, self.soft_score)
    }
    
}

unsafe impl Send for HardMediumSoftScore {}