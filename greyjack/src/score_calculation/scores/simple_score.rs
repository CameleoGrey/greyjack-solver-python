


use pyo3::prelude::*;
use crate::utils::math_utils::round;
use std::cmp::Ordering;
use std::ops::{Add, AddAssign};
use std::fmt::{Display, Formatter};

#[pyclass(str, eq, ord)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct SimpleScore {
    pub simple_value: f64
}

#[pymethods]
impl SimpleScore {

    #[new]
    #[pyo3(signature = (simple_value))]
    pub fn new(simple_value: f64) -> Self {
        SimpleScore{
            simple_value
        }
    }

    #[getter]
    pub fn get_simple_value(&self) -> f64 {
        self.simple_value
    }

    #[setter]
    pub fn set_simple_value(&mut self, value: f64) {
        self.simple_value = value;
    }

    pub fn get_sum_abs(&self) -> f64 {
        self.simple_value.abs()
    }

    pub fn get_priority_score(&self) -> f64 {
        self.simple_value
    }

    pub fn get_fitness_value(&self) -> f64 {
        1.0 - (1.0 / (self.simple_value + 1.0))
    }

    #[staticmethod]
    pub fn get_null_score() -> Self {
        SimpleScore {
            simple_value: 0.0
        }
    }

    #[staticmethod]
    pub fn get_stub_score() -> Self {
        SimpleScore {
            simple_value: f64::MAX - 1.0
        }
    }

    pub fn mul(&self, scalar: f64) -> Self {
        SimpleScore {
            simple_value: scalar * self.simple_value,
        }
    }

    #[staticmethod]
    pub fn precision_len() -> usize {
        1
    }

    pub fn round(&mut self, precision: Vec<u64>) {
        self.simple_value = round(self.simple_value, precision[0]);
    }

    pub fn __add__(&self, rhs: &Self) -> Self {
        Self {
            simple_value: self.simple_value + rhs.simple_value,
        }
    }
    
    pub fn __repr__(&self) -> String {
        return self.simple_value.to_string();
    }

    pub fn as_list(&self) -> Vec<f64> {
        vec![self.simple_value]
    }

    #[staticmethod]
    pub fn from_list(score_list: Vec<f64>) -> Self {
        Self {
            simple_value: score_list[0],
        }
    }

}

impl Eq for SimpleScore {}

impl Ord for SimpleScore {

    fn cmp(&self, other: &Self) -> Ordering {
        self.simple_value.total_cmp(&other.simple_value)
    }
    
}

impl Add for SimpleScore {
    type Output = Self;

    fn add(self, rhs: Self) -> Self::Output {
        SimpleScore {
            simple_value: self.simple_value + rhs.simple_value,
        }
    }
}

impl AddAssign for SimpleScore {
    fn add_assign(&mut self, rhs: Self) {
        self.simple_value += rhs.simple_value;
    }
}

impl Display for SimpleScore {

    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.simple_value)
    }
    
}