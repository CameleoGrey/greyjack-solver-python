

use pyo3::{prelude::*, wrap_pymodule, py_run};
mod score_calculation;
mod variables;
mod utils;
mod agents;
use score_calculation::scores::*;

build_concrete_individual!(IndividualSimple, SimpleScore);
build_concrete_individual!(IndividualHardSoft, HardSoftScore);
build_concrete_individual!(IndividualHardMediumSoft, HardMediumSoftScore);

use crate::score_calculation::score_requesters::{VariablesManagerPy, VariablesManager};
use crate::agents::base::metaheuristic_bases::Mover;
use rand_distr::num_traits::ToPrimitive;
use std::collections::HashMap;
use std::collections::VecDeque;
use std::collections::HashSet;
use std::cmp::max;
build_concrete_tabu_search_base!(TabuSearchSimple, IndividualSimple, SimpleScore);
build_concrete_tabu_search_base!(TabuSearchHardSoft, IndividualHardSoft, HardSoftScore);
build_concrete_tabu_search_base!(TabuSearchHardMediumSoft, IndividualHardMediumSoft, HardMediumSoftScore);

use rand::SeedableRng;
use rand::rngs::StdRng;
use rand_distr::{Distribution, Uniform};
use crate::utils::math_utils;
build_concrete_genetic_algorithm_base!(GeneticAlgorithmSimple, IndividualSimple, SimpleScore);
build_concrete_genetic_algorithm_base!(GeneticAlgorithmHardSoft, IndividualHardSoft, HardSoftScore);
build_concrete_genetic_algorithm_base!(GeneticAlgorithmHardMediumSoft, IndividualHardMediumSoft, HardMediumSoftScore);

build_concrete_late_acceptance_base!(LateAcceptanceSimple, IndividualSimple, SimpleScore);
build_concrete_late_acceptance_base!(LateAcceptanceHardSoft, IndividualHardSoft, HardSoftScore);
build_concrete_late_acceptance_base!(LateAcceptanceHardMediumSoft, IndividualHardMediumSoft, HardMediumSoftScore);

build_concrete_simulated_annealing_base!(SimulatedAnnealingSimple, IndividualSimple, SimpleScore);
build_concrete_simulated_annealing_base!(SimulatedAnnealingHardSoft, IndividualHardSoft, HardSoftScore);
build_concrete_simulated_annealing_base!(SimulatedAnnealingHardMediumSoft, IndividualHardMediumSoft, HardMediumSoftScore);

use std::fmt::Debug;
use rand_distr::Normal;
use rand::Rng;
use rand::seq::SliceRandom;
use std::f64::consts::PI;
use rand::prelude::IteratorRandom;

build_concrete_lshade_base!(LSHADESimple, IndividualSimple, SimpleScore);
build_concrete_lshade_base!(LSHADEHardSoft, IndividualHardSoft, HardSoftScore);
build_concrete_lshade_base!(LSHADEHardMediumSoft, IndividualHardMediumSoft, HardMediumSoftScore);

build_concrete_sum_scores_function!(sum_simple_scores, SimpleScore);
build_concrete_sum_scores_function!(sum_hard_soft_scores, HardSoftScore);
build_concrete_sum_scores_function!(sum_hard_medium_soft_scores, HardMediumSoftScore);


#[pymodule]
fn greyjack(py: Python, m: &Bound<PyModule>) -> PyResult<()> {

    // greyjack.variables
    m.add_class::<variables::GJPlanningVariablePy>()?;

    // greyjack.scores
    m.add_class::<score_calculation::scores::SimpleScore>()?;
    m.add_class::<score_calculation::scores::HardSoftScore>()?;
    m.add_class::<score_calculation::scores::HardMediumSoftScore>()?;

    // greyjack.base
    m.add_class::<IndividualSimple>()?;
    m.add_class::<IndividualHardSoft>()?;
    m.add_class::<IndividualHardMediumSoft>()?;

    // greyjack.score_calculation.score_requesters
    m.add_class::<score_calculation::score_requesters::VariablesManagerPy>()?;
    m.add_class::<score_calculation::score_requesters::CandidateDfsBuilderPy>()?;

    // greyjack.agents.base.metaheuristic_bases
    m.add_class::<TabuSearchSimple>()?;
    m.add_class::<TabuSearchHardSoft>()?;
    m.add_class::<TabuSearchHardMediumSoft>()?;
    m.add_class::<GeneticAlgorithmSimple>()?;
    m.add_class::<GeneticAlgorithmHardSoft>()?;
    m.add_class::<GeneticAlgorithmHardMediumSoft>()?;
    m.add_class::<LateAcceptanceSimple>()?;
    m.add_class::<LateAcceptanceHardSoft>()?;
    m.add_class::<LateAcceptanceHardMediumSoft>()?;
    m.add_class::<SimulatedAnnealingSimple>()?;
    m.add_class::<SimulatedAnnealingHardSoft>()?;
    m.add_class::<SimulatedAnnealingHardMediumSoft>()?;
    m.add_class::<LSHADESimple>()?;
    m.add_class::<LSHADEHardSoft>()?;
    m.add_class::<LSHADEHardMediumSoft>()?;

    let _ = m.add_function(wrap_pyfunction!(sum_simple_scores, m)?);
    let _ = m.add_function(wrap_pyfunction!(sum_hard_soft_scores, m)?);
    let _ = m.add_function(wrap_pyfunction!(sum_hard_medium_soft_scores, m)?);

    Ok(())
}