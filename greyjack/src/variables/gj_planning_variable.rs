
use std::cmp::Ordering::*;
use rand::SeedableRng;
use rand::rngs::StdRng;
use rand_distr::{Normal, Distribution, Uniform};
use crate::utils::math_utils::rint;

#[derive(Clone, Debug)]
pub struct GJPlanningVariable {
    pub name: String,
    pub initial_value: Option<f64>,
    pub lower_bound: f64,
    pub upper_bound: f64,
    pub frozen: bool,
    pub random_generator: StdRng,
    pub uniform_distribution: Uniform<f64>,
    pub normal_distribution: Option<Normal<f64>>,
    pub semantic_groups: Vec<String>,
    pub is_int: bool,
}

impl GJPlanningVariable {
    pub fn new(name: String, lower_bound: f64, upper_bound: f64, frozen: bool, is_int: bool, initial_value: Option<f64>, semantic_groups: Option<Vec<String>>)  -> Self {
            
            let normal_distribution;
            match initial_value {
                None => normal_distribution = None,
                Some(x) => normal_distribution = Some(Normal::new(x, 0.1).unwrap())
            };

            let mut current_semantic_groups: Vec<String> = Vec::new();
            match semantic_groups {
                None => current_semantic_groups.push("common".to_string()),
                Some(groups) => {
                    for group in groups {
                        current_semantic_groups.push(group);
                    }
                },
            }

            Self {
                name: name.to_string(),
                initial_value: initial_value,
                lower_bound: lower_bound,
                upper_bound: upper_bound,
                frozen: frozen,
                random_generator: StdRng::from_entropy(),
                uniform_distribution: Uniform::new_inclusive(lower_bound, upper_bound),
                normal_distribution: normal_distribution,
                semantic_groups: current_semantic_groups,
                is_int: is_int,
            }
        }

    pub fn set_name(&mut self, new_name: String) {
        self.name = new_name;
    }

    pub fn fix(&self, value: f64) -> f64 {

        if self.frozen {
            match self.initial_value {
                Some(x) => return x,
                None => panic!("Frozen value must be initialized")
            }
        }
        
        let mut fixed_value = Self::min(Self::max(value, self.lower_bound), self.upper_bound);
        if self.is_int {
            fixed_value = rint(fixed_value);
        }

        return fixed_value;
    }

    pub fn sample(&mut self) -> f64 {

        if self.frozen {
            match self.initial_value {
                Some(x) => return x,
                None => panic!("Frozen value must be initialized")
            }
        }

        let sampled_value: f64 = self.uniform_distribution.sample( &mut self.random_generator);
        return sampled_value;
    }

    pub fn get_initial_value(&mut self) -> f64 {

        match self.initial_value {
            None => {
                let mut sampled_value = self.sample();
                if self.is_int {
                    sampled_value = rint(sampled_value);
                }
                return sampled_value;
            },
            Some(x) => {
                let mut initial_value = x;
                if self.frozen {
                    return initial_value;
                }
                return initial_value;
            }
        }
    }

    pub fn min(a: f64, b: f64) -> f64 {

        let min_value;
        match a.total_cmp(&b) {
            Less => min_value = a,
            Greater => min_value = b,
            Equal => min_value = a
        }
        min_value
    }

    pub fn max(a: f64, b: f64) -> f64 {

        let max_value;
        match a.total_cmp(&b) {
            Less => max_value = b,
            Greater => max_value = a,
            Equal => max_value = b
        }
        max_value
    }

}