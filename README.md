
# Preview

![](logos/greyjack-python-long-logo.png)

_In optimum we trust._

GreyJack Solver is a "jack of all trades" constraint metaheuristic solver for Python, built on the robust foundations of Rust and Polars. It empowers you to tackle a wide array of constraint optimization problems, including continuous, integer, and mixed-integer challenges with ease and efficiency.

# Editions

There are 2 editions of GreyJack Solver:

- Python edition
- [Rust edition](https://github.com/CameleoGrey/greyjack-solver-rust)

# Key Features of GreyJack Solver

- **Unmatched Comfort, Expressiveness, Flexibility and speed of developing** Designed to express almost any optimization problem with maximum comfortability and clarity.
- **Universality** Supports a wide range of constraint problems, including continuous, integer, and mixed-integer challenges. Additionally, thanks to Polars, you can optimize virtually any process that can be represented as table data.
- **Python's Comfort Meets Rust's Speed** All computationally intensive parts of the solver are implemented in Rust and seamlessly integrated into Python, offering fast development cycles with production-ready performance for ~95% real-world tasks.
- **Clarity and Simplicity** GreyJack provides a clear and straightforward approach to designing, implementing, and improving effective solutions for nearly any constraint problem and scenario.
- **Nearly Linear Horizontal Scaling** The multi-threaded solving process is organized as a collective effort of individual agents (using the island computation model for all algorithms), which share results with neighbors during solving. This approach ensures nearly linear horizontal scaling, enhancing both the quality and speed of solutions (depending on agent settings and the problem at hand).
- **Support for Population and Local Search Algorithms** GreyJack Solver supports a wide range of metaheuristics, including population-based and local search algorithms, with highly flexible settings. You can easily find, select, and configure the approach that best fits your problem, delivering optimal results.
- **Easy Integration**  The observer mechanism (see examples) simplifies integration, making it straightforward to incorporate GreyJack Solver into your existing workflows..

# Get started with GreyJack Solver

```
pip install greyjack
```

- Explore examples. Docs and guides will be later. GreyJack is very intuitively understandable solver (even Rust version).
- Simply solve your tasks simply.

# Install GreyJack Solver from source

- Be sure that you've installed Rust (rustup) and Python on your machine.
```
- (create venv, activate it, cd greyjack-solver-python/greyjack)
pip install maturin
maturin develop --release
```
-  maturin will build the Rust part, get all Python dependencies (for solver itself, not examples) and install greyjack to your venv

# RoadMap
- Add more examples: Job-Shop, Pickup&Delivery, some continuous and MIP tasks, scheduling, etc
- Types, arguments validation
- Write docs
- Tests, tests, tests...
- Composite termination criterion (for example: solving limit minutes N AND score not improving M seconds)
- Multi-level score
- Custom moves support
- Try to impove incremental (pseudo-incremental) score calculation mechanism (caching, no clonning, etc)
- Website
- Useful text materials, guides, presentations
- Score explainer / interpreter for OOP API