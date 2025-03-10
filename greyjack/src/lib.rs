

use pyo3::{prelude::*, wrap_pymodule, py_run};
mod score_calculation;
mod variables;
mod utils;
mod agents;

use score_calculation::scores::*;
build_concrete_individual!(IndividualSimple, SimpleScore);
build_concrete_individual!(IndividualHardSoft, HardSoftScore);
build_concrete_individual!(IndividualHardMediumSoft, HardMediumSoftScore);

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

    m.add_class::<score_calculation::score_requesters::VariablesManagerPy>()?;
    m.add_class::<score_calculation::score_requesters::CandidateDfsBuilderPy>()?;

    //py.import("sys")?.getattr("modules")?.set_item("greyjack.greyjack", m)?;
    //py_run!(py, m, "import sys; sys.modules['greyjack.greyjack'] = greyjack");

    /*let mut planning_vec: Vec<GJPlanningVariable> = Vec::new();
    planning_vec.push(GJPlanningVariable::new("x1".to_string(), 0.1, 1.0, false, false, None, None).unwrap());
    planning_vec.push(GJPlanningVariable::new("x1".to_string(), 10.0, 100.0, false, true, None, None).unwrap());
    println!("{:?}", planning_vec);*/

    Ok(())
}

/*#[pymodule]
fn variables_module(py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<variables::GJFloat>()?;
    Ok(())
}*/

/*#[pymodule]
fn greyjack(py: Python, m: &Bound<PyModule>) -> PyResult<()> {

    m.add_wrapped(wrap_pymodule!(variables_module))?;
    

    Ok(())
}*/

/*#[pymodule]
fn greyjack(py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    module.add_wrapped(wrap_pymodule!(submodule))?;

    py.import("sys")?
        .getattr("modules")?
        .set_item("supermodule.submodule", submodule)?;

    Ok(())
}*/

/*#[pymodule]
fn greyjack(py: Python, module: &Bound<PyModule>) -> PyResult<()> {
    let variables_module = PyModule::new(py, "greyjack.variables")?;
    // py_run! is quick-and-dirty; should be replaced by PyO3 API calls in actual code
    py_run!(py, variables_module, "import sys; sys.modules['greyjack.variables'] = variables");
    // this is actually not needed now that we don't trigger the import mechanism...
    // module.setattr("__path__", PyList::empty(py))?;
    module.add_submodule(&variables_module)?;

    Ok(())
}*/
