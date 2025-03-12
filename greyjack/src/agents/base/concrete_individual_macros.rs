
#[macro_export]
macro_rules! build_concrete_individual {
    ($name: ident, $score_type: ident) => {

            #[pyclass(str, eq, ord)]
            #[derive(Debug, Clone)]
            pub struct $name {
                pub variable_values: Vec<f64>,
                pub score: $score_type,
            }
            
            #[pymethods]
            impl $name {
                #[new]
                pub fn new(variable_values: Vec<f64>, score: $score_type) -> Self {
                    Self {
                        variable_values: variable_values,
                        score: score
                    }
                }

                #[getter]
                pub fn variable_values(&self) -> PyResult<Vec<f64>> {
                    Ok(self.variable_values.clone())
                }

                #[getter]
                pub fn score(&self) -> PyResult<$score_type> {
                    Ok(self.score.clone())
                }
                
                pub fn as_list(&self) -> Vec<Vec<f64>> {
                    vec![self.variable_values.clone(), self.score.as_list()]
                }

                pub fn copy(&self) -> Self {
                    self.clone()
                }
                
                #[staticmethod]
                pub fn from_list(list_individual: Vec<Vec<f64>>) -> Self {
                    Self {
                        variable_values: list_individual[0].clone(),
                        score: $score_type::from_list(list_individual[1].clone())
                    }
                }

                #[staticmethod]
                pub fn convert_individuals_to_lists(individuals_list: Vec<Self>) -> Vec<Vec<Vec<f64>>> {
                    let list_individuals: Vec<Vec<Vec<f64>>> = individuals_list.iter().map(|individual| individual.as_list()).collect();
                    return list_individuals;
                }

                #[staticmethod]
                pub fn convert_lists_to_individuals(list_individuals: Vec<Vec<Vec<f64>>>) -> Vec<Self> {
                    let individuals_list: Vec<Self> = list_individuals.iter().map(|list_individual| Self::from_list(list_individual.clone())).collect();
                    return individuals_list;
                }
            }

            impl Ord for $name {

                fn cmp(&self, other: &$name) -> std::cmp::Ordering {
                    self.score.cmp(&other.score)
                }
                
            }

            impl Eq for $name {
                
            }

            impl PartialEq for $name {
                fn eq(&self, other: &$name) -> bool {
                    self.score.eq(&other.score)
                }

                fn ne(&self, other: &$name) -> bool {
                    self.score.ne(&other.score)
                }
            }

            impl PartialOrd for $name {
                fn partial_cmp(&self, other: &$name) -> Option<std::cmp::Ordering> {
                    self.score.partial_cmp(&other.score)
                }
            }

            impl std::fmt::Display for $name {

                fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                    write!(f, "{:?}", self.score)
                }
                
            }
    };
}
