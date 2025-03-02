use pyo3::{prelude::*, wrap_pymodule, py_run};
use variables::GJPlanningVariable;

mod variables;
mod utils;



#[pymodule]
fn greyjack(py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<variables::GJPlanningVariable>()?;
    m.add_class::<variables::GJFloat>()?;
    m.add_class::<variables::GJInteger>()?;

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
