

use pyo3::prelude::*;


#[pyclass]
#[derive(FromPyObject, Debug)]
pub struct GJPlanningVariablePy {
    pub name: String,
    pub initial_value: Option<f64>,
    pub lower_bound: f64,
    pub upper_bound: f64,
    pub frozen: bool,
    pub semantic_groups: Vec<String>,
    pub is_int: bool,
}

#[pymethods]
impl GJPlanningVariablePy {

    #[getter]
    pub fn name(&self) -> PyResult<String> {
        Ok(self.name.clone())
    }

    #[setter]
    fn set_name(&mut self, name: String) -> PyResult<()> {
        self.name = name;
        Ok(())
    }
    

    #[getter]
    pub fn initial_value(&self) -> PyResult<Option<f64>> {
        Ok(self.initial_value.clone())
    }

    #[getter]
    pub fn lower_bound(&self) -> PyResult<f64> {
        Ok(self.lower_bound)
    }

    #[getter]
    pub fn upper_bound(&self) -> PyResult<f64> {
        Ok(self.upper_bound)
    }

    #[getter]
    pub fn frozen(&self) -> PyResult<bool> {
        Ok(self.frozen)
    }

    #[getter]
    pub fn semantic_groups(&self) -> PyResult<Vec<String>> {
        Ok(self.semantic_groups.clone())
    }

    #[getter]
    pub fn is_int(&self) -> PyResult<bool> {
        Ok(self.is_int)
    }

    #[new]
    #[pyo3(signature = (lower_bound, upper_bound, frozen, is_int, initial_value=None, semantic_groups=None))]
    pub fn new(lower_bound: f64, upper_bound: f64, frozen: bool, is_int: bool, initial_value: Option<f64>, semantic_groups: Option<Vec<String>>)  -> PyResult<Self> {
        
        let mut current_semantic_groups: Vec<String> = Vec::new();
            match semantic_groups {
                None => current_semantic_groups.push("common".to_string()),
                Some(groups) => {
                    for group in groups {
                        current_semantic_groups.push(group);
                    }
                },
            }
        
        Ok(GJPlanningVariablePy {
            name: "".to_string(),
            initial_value: initial_value,
            lower_bound: lower_bound,
            upper_bound: upper_bound,
            frozen: frozen,
            semantic_groups: current_semantic_groups,
            is_int: is_int,
        })
    }
}