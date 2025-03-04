

use pyo3::prelude::*;


#[pyclass]
#[derive(FromPyObject)]
pub struct GJPlanningVariablePy {
    pub name: String,
    pub initial_value: Option<f64>,
    pub lower_bound: f64,
    pub upper_bound: f64,
    pub frozen: bool,
    pub semantic_groups: Option<Vec<String>>,
    pub is_int: bool,
}

#[pymethods]
impl GJPlanningVariablePy {
    
    #[new]
    #[pyo3(signature = (name, lower_bound, upper_bound, frozen, is_int, initial_value=None, semantic_groups=None))]
    pub fn new(name: String, lower_bound: f64, upper_bound: f64, frozen: bool, is_int: bool, initial_value: Option<f64>, semantic_groups: Option<Vec<String>>)  -> PyResult<Self> {
        Ok(GJPlanningVariablePy {
            name: name.to_string(),
            initial_value: initial_value,
            lower_bound: lower_bound,
            upper_bound: upper_bound,
            frozen: frozen,
            semantic_groups: semantic_groups,
            is_int: is_int,
        })
    }
}