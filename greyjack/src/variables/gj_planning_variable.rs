use super::super::utils::rng_utils::RngUtils;
use super::super::utils::math_utils::rint;

#[derive(Clone, Debug)]
pub struct GJPlanningVariable {
    pub name: String,
    pub initial_value: Option<f64>,
    pub lower_bound: f64,
    pub upper_bound: f64,
    pub frozen: bool,
    pub semantic_groups: Vec<String>,
    pub is_int: bool,
    // REMOVED: Individual RNG instances - use centralized instead
    // pub random_generator: StdRng,
    // pub uniform_distribution: Uniform<f64>,
    // pub normal_distribution: Option<Normal<f64>>,
}

impl GJPlanningVariable {
    pub fn new(
        name: String,
        lower_bound: f64,
        upper_bound: f64,
        frozen: bool,
        is_int: bool,
        initial_value: Option<f64>,
        semantic_groups: Option<Vec<String>>,
    ) -> Self {
        let current_semantic_groups = semantic_groups.unwrap_or_else(|| vec!["common".to_string()]);

        Self {
            name,
            initial_value,
            lower_bound,
            upper_bound,
            frozen,
            semantic_groups: current_semantic_groups,
            is_int,
        }
    }

    pub fn set_name(&mut self, new_name: String) {
        self.name = new_name;
    }

    pub fn fix(&self, value: f64) -> f64 {
        if self.frozen {
            return self.initial_value.expect("Frozen value must be initialized");
        }

        let mut fixed_value = value.clamp(self.lower_bound, self.upper_bound);
        if self.is_int {
            fixed_value = rint(fixed_value);
        }

        fixed_value
    }

    // FIXED: Use centralized RNG
    pub fn sample(&self) -> f64 {
        if self.frozen {
            return self.initial_value.expect("Frozen value must be initialized");
        }

        RngUtils::get_random_f64_range(self.lower_bound, self.upper_bound)
    }

    // FIXED: Use centralized RNG
    pub fn get_initial_value(&self) -> f64 {
        match self.initial_value {
            None => {
                let mut sampled_value = self.sample();
                if self.is_int {
                    sampled_value = rint(sampled_value);
                }
                sampled_value
            }
            Some(initial_value) => initial_value,
        }
    }

    pub fn min(a: f64, b: f64) -> f64 {
        a.min(b)
    }

    pub fn max(a: f64, b: f64) -> f64 {
        a.max(b)
    }
}