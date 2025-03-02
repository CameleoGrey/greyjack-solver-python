use pyo3::prelude::*;
use std::cmp::Ordering::*;
use rand::SeedableRng;
use rand::rngs::StdRng;
use rand_distr::{Normal, Distribution, Uniform};
use crate::variables::GJPlanningVariable;

#[pyclass(extends=GJPlanningVariable)]
#[derive(Clone)]
pub struct GJInteger {
}

#[pymethods]
impl GJInteger {
    #[new]
    #[pyo3(signature = (name, lower_bound, upper_bound, frozen, initial_value=None, semantic_groups=None))]
    fn new(name: String, lower_bound: f64, upper_bound: f64, frozen: bool, initial_value: Option<f64>, semantic_groups: Option<Vec<String>>) -> (Self, GJPlanningVariable) {
        (GJInteger{}, GJPlanningVariable::new(name, lower_bound, upper_bound, frozen, true, initial_value, semantic_groups).unwrap())
    }
}