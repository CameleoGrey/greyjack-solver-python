"""Public native move contracts, with bounded children for search operations."""

import json
import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from greyjack import greyjack as native
from greyjack.agents import (
    GeneticAlgorithm,
    LSHADE,
    LateAcceptance,
    SimulatedAnnealing,
    TabuSearch,
)
from greyjack.agents.metaheuristic_bases.GeneticAlgorithmBase import (
    GeneticAlgorithmBase,
)
from greyjack.agents.metaheuristic_bases.LateAcceptanceBase import LateAcceptanceBase
from greyjack.agents.metaheuristic_bases.LSHADEBase import LSHADEBase
from greyjack.agents.metaheuristic_bases.SimulatedAnnealingBase import (
    SimulatedAnnealingBase,
)
from greyjack.agents.metaheuristic_bases.TabuSearchBase import TabuSearchBase
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.agents.termination_strategies.StepsLimit import StepsLimit
from greyjack.cotwin.CotwinBase import CotwinBase
from greyjack.score_calculation.score_calculators.PlainScoreCalculator import (
    PlainScoreCalculator,
)
from greyjack.variables.GJInteger import GJInteger


OPERATORS = ("change", "swap", "swap_edges", "scramble", "insertion", "inverse")
MINIMUM_SIZES = (1, 2, 3, 3, 2, 2)
LOCAL_ALGORITHMS = ("tabu", "late", "annealing")
ALGORITHMS = LOCAL_ALGORITHMS + ("genetic", "lshade")
SCORES = (
    (ScoreVariants.SimpleScore, native.SimpleScore, native.IndividualSimple, 1),
    (ScoreVariants.HardSoftScore, native.HardSoftScore, native.IndividualHardSoft, 2),
    (
        ScoreVariants.HardMediumSoftScore,
        native.HardMediumSoftScore,
        native.IndividualHardMediumSoft,
        3,
    ),
)


def variable(
    lower=0, upper=20, *, initial=None, frozen=False, integer=True, groups=None
):
    return native.GJPlanningVariablePy(lower, upper, frozen, integer, initial, groups)


def variables_manager(variables):
    for index, current in enumerate(variables):
        current.name = f"x{index}"
    return native.VariablesManagerPy(variables)


def make_method(
    algorithm,
    manager,
    score_index=0,
    *,
    weights=None,
    tabu_rate=0.0,
    multiplier=None,
    groups=None,
):
    variant, _, _, levels = SCORES[score_index]
    groups = manager.semantic_groups_map if groups is None else groups
    discrete = manager.discrete_ids
    if algorithm == "tabu":
        return TabuSearchBase.new(
            variant, manager, 8, tabu_rate, groups, multiplier, weights, discrete
        )
    if algorithm == "late":
        return LateAcceptanceBase.new(
            variant, manager, 4, tabu_rate, groups, multiplier, weights, discrete
        )
    if algorithm == "annealing":
        return SimulatedAnnealingBase.new(
            variant,
            manager,
            [1.0] * levels,
            tabu_rate,
            groups,
            0.99,
            multiplier,
            weights,
            discrete,
        )
    if algorithm == "genetic":
        return GeneticAlgorithmBase.new(
            variant,
            manager,
            8,
            0.5,
            0.5,
            tabu_rate,
            groups,
            multiplier,
            weights,
            discrete,
        )
    return LSHADEBase.new(
        variant,
        manager,
        8,
        8,
        0.5,
        0.0,
        1,
        0.5,
        0.5,
        0.5,
        tabu_rate,
        groups,
        multiplier,
        weights,
        discrete,
    )


def score_values(values, score_index):
    """An independently reconstructed objective, sensitive to value positions."""
    levels = SCORES[score_index][3]
    total = sum((index + 1) * value * value for index, value in enumerate(values))
    return [0.0] * (levels - 1) + [total]


def scored(values, score_index):
    _, score_type, individual_type, _ = SCORES[score_index]
    return individual_type(list(values), score_type(*score_values(values, score_index)))


def assert_values(values, variables):
    assert len(values) == len(variables)
    for value, current in zip(values, variables):
        assert math.isfinite(value)
        assert current.lower_bound <= value <= current.upper_bound
        if current.is_int:
            assert int(value) == value
        if current.frozen:
            assert value == current.initial_value
        if current.lower_bound == current.upper_bound:
            assert value == current.lower_bound


def assert_scored_population(population, variables, score_index):
    assert population
    for individual in population:
        assert_values(individual.variable_values, variables)
        assert individual.score.as_list() == pytest.approx(
            score_values(individual.variable_values, score_index)
        )


def replay_deltas(baseline, changes, variables):
    assert changes, "Even an identity move must retain its candidate's delta rows"
    identifiers = [index for index, _ in changes]
    assert len(identifiers) == len(set(identifiers)), changes
    assert all(
        type(index) is int and 0 <= index < len(baseline) for index in identifiers
    )
    result = list(baseline)
    for index, value in changes:
        assert not variables[index].frozen
        assert variables[index].lower_bound != variables[index].upper_bound
        result[index] = value
    assert_values(result, variables)
    return result


def exercise_local(method, variables, baseline, score_index, operator=None, rounds=6):
    population = [scored(baseline, score_index)]
    original = population[0].as_list()
    for _ in range(rounds):
        candidates = method.sample_candidates_plain(population, population[0])
        assert candidates
        for candidate in candidates:
            assert_values(candidate, variables)
            if operator is not None and operator != 0:
                assert sorted(candidate) == sorted(baseline)
        updated = method.build_updated_population(
            population, [scored(values, score_index) for values in candidates]
        )
        assert_scored_population(updated, variables, score_index)

        sample, deltas = method.sample_candidates_incremental(population, population[0])
        assert sample == baseline
        assert deltas
        replayed = [replay_deltas(sample, change, variables) for change in deltas]
        if operator is not None and operator != 0:
            assert all(sorted(candidate) == sorted(baseline) for candidate in replayed)
        score_type = SCORES[score_index][1]
        updated, committed = method.build_updated_population_incremental(
            population,
            sample,
            deltas,
            [score_type(*score_values(values, score_index)) for values in replayed],
        )
        assert_scored_population(updated, variables, score_index)
        if committed is None:
            assert updated[0].as_list() == original
        else:
            assert updated[0].variable_values == replay_deltas(
                sample, committed, variables
            )
        # Candidate generation and reconstruction must not overwrite its input.
        assert population[0].as_list() == original
        assert sample == baseline


def operator_contract(operator, size):
    weights = [float(index == operator) for index in range(len(OPERATORS))]
    variables = [variable(initial=index + 1) for index in range(size)]
    manager = variables_manager(variables)
    baseline = manager.sample_variables()
    for algorithm in LOCAL_ALGORITHMS:
        for score_index in range(len(SCORES)):
            if size < MINIMUM_SIZES[operator]:
                with pytest.raises(
                    ValueError, match="(?i)(eligible|mutable|group|variable|move)"
                ):
                    method = make_method(
                        algorithm, manager, score_index, weights=weights
                    )
                    population = [scored(baseline, score_index)]
                    method.sample_candidates_plain(population, population[0])
                continue
            for tabu_rate in (0.0, 1.0):
                method = make_method(
                    algorithm,
                    manager,
                    score_index,
                    weights=weights,
                    tabu_rate=tabu_rate,
                    multiplier=1.0 if tabu_rate else None,
                )
                exercise_local(
                    method, variables, baseline, score_index, operator=operator
                )


def default_portfolio_contract(size):
    variables = [variable(initial=index + 1) for index in range(size)]
    manager = variables_manager(variables)
    baseline = manager.sample_variables()
    for algorithm in ALGORITHMS:
        for score_index in range(len(SCORES)):
            method = make_method(algorithm, manager, score_index)
            if algorithm in LOCAL_ALGORITHMS:
                exercise_local(method, variables, baseline, score_index)
                continue
            population = [scored(baseline, score_index) for _ in range(8)]
            for _ in range(6):
                samples = method.sample_candidates_plain(population, population[0])
                assert len(samples) == len(population)
                assert all(len(sample) == size for sample in samples)
                candidates = [scored(sample, score_index) for sample in samples]
                assert_scored_population(candidates, variables, score_index)
                population = method.build_updated_population(population, candidates)
                assert_scored_population(population, variables, score_index)
                population.sort()


def mixed_groups_contract(operator):
    variables = [
        variable(-5, 5, initial=2, frozen=True, groups=["frozen", "shared"]),
        variable(3.5, 3.5, integer=False, groups=["fixed", "shared"]),
        variable(-3, 3, integer=False, initial=1.25, frozen=True, groups=["empty"]),
        variable(0, 12, initial=4, groups=["mutable", "mutable"]),
        variable(
            -2.5, 6.75, initial=3.125, integer=False, groups=["mutable", "shared"]
        ),
        variable(-7, -1, initial=-3, groups=["mutable"]),
        variable(-100, 100, initial=10.5, integer=False, groups=["mutable"]),
        variable(5, 25, initial=17, groups=["mutable"]),
    ]
    manager = variables_manager(variables)
    baseline = manager.sample_variables()
    groups = manager.semantic_groups_map
    for identifiers in groups.values():
        assert len(identifiers) == len(set(identifiers))
        assert all(0 <= index < len(variables) for index in identifiers)
    groups["explicitly_empty"] = []
    weights = [float(index == operator) for index in range(len(OPERATORS))]
    for algorithm in LOCAL_ALGORITHMS:
        for score_index in range(len(SCORES)):
            method = make_method(
                algorithm,
                manager,
                score_index,
                weights=weights,
                groups=groups,
                tabu_rate=1.0,
            )
            exercise_local(method, variables, baseline, score_index, rounds=8)


def no_eligible_contract(kind):
    for algorithm in ALGORITHMS:
        with pytest.raises(
            ValueError, match="(?i)(eligible|mutable|group|variable|move)"
        ):
            if kind == "empty_variables":
                variables = []
            elif kind == "empty_groups":
                variables = [variable(initial=2, groups=[])]
            elif kind == "frozen":
                variables = [variable(initial=2, frozen=True)]
            else:
                variables = [variable(2, 2)]
            manager = variables_manager(variables)
            method = make_method(algorithm, manager)
            baseline = manager.sample_variables()
            population = [
                scored(baseline, 0)
                for _ in range(8 if algorithm in ("genetic", "lshade") else 1)
            ]
            method.sample_candidates_plain(population, population[0])


def disjoint_groups_contract():
    group_a, group_b = {0, 2, 5}, {1, 3, 4, 6}
    variables = [
        variable(initial=index + 1, groups=["A" if index in group_a else "B"])
        for index in range(7)
    ]
    manager = variables_manager(variables)
    baseline = manager.sample_variables()
    for operator in range(len(OPERATORS)):
        weights = [float(index == operator) for index in range(len(OPERATORS))]
        method = make_method(
            "tabu", manager, weights=weights, tabu_rate=1.0, multiplier=1.0
        )
        population = [scored(baseline, 0)]
        for _ in range(8):
            candidates = method.sample_candidates_plain(population, population[0])
            sample, deltas = method.sample_candidates_incremental(
                population, population[0]
            )
            assert sample == baseline
            for change in deltas:
                indices = {index for index, _ in change}
                assert indices <= group_a or indices <= group_b
                candidates.append(replay_deltas(sample, change, variables))
            for candidate in candidates:
                assert_values(candidate, variables)
                changed = {
                    index
                    for index, (old, new) in enumerate(zip(baseline, candidate))
                    if old != new
                }
                assert changed <= group_a or changed <= group_b
                if operator != 0:
                    for group in (group_a, group_b):
                        assert sorted(candidate[index] for index in group) == sorted(
                            baseline[index] for index in group
                        )


def identical_lshade_contract(score_index):
    variables = [variable(-10, 10, integer=False, initial=0.0) for _ in range(4)]
    manager = variables_manager(variables)
    for distinct in (1, 2):
        method = make_method("lshade", manager, score_index)
        population = [
            scored([float(index % distinct)] * 4, score_index) for index in range(8)
        ]
        population.sort()
        for _ in range(16):
            samples = method.sample_candidates_plain(population, population[0])
            assert len(samples) == len(population)
            assert_scored_population(
                [scored(values, score_index) for values in samples],
                variables,
                score_index,
            )


def run_bounded(tmp_path, case, *parameters):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), case, *map(str, parameters)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, (
        f"{case} {parameters}\n{result.stdout}\n{result.stderr}"
    )
    assert json.loads(result.stdout.splitlines()[-1]) == {"case": case, "passed": True}


@pytest.mark.parametrize("size", range(1, 8))
@pytest.mark.parametrize("operator", range(len(OPERATORS)), ids=OPERATORS)
def test_one_hot_operator_contracts_and_minimum_group_sizes(tmp_path, operator, size):
    run_bounded(tmp_path, "operator", operator, size)


@pytest.mark.parametrize("size", range(1, 8))
def test_default_portfolio_all_algorithms_and_scores_on_small_groups(tmp_path, size):
    run_bounded(tmp_path, "default", size)


@pytest.mark.parametrize("operator", range(len(OPERATORS)), ids=OPERATORS)
def test_mixed_groups_incremental_ids_frozen_values_and_bounds(tmp_path, operator):
    run_bounded(tmp_path, "mixed", operator)


@pytest.mark.parametrize("kind", ["empty_variables", "empty_groups", "frozen", "fixed"])
def test_no_eligible_mutable_group_fails_clearly(tmp_path, kind):
    run_bounded(tmp_path, "ineligible", kind)


def test_noncontiguous_semantic_groups_are_never_combined_by_a_move(tmp_path):
    run_bounded(tmp_path, "disjoint_groups")


@pytest.mark.parametrize("score_index", range(len(SCORES)))
def test_lshade_identical_or_two_distinct_vectors_terminate(tmp_path, score_index):
    run_bounded(tmp_path, "identical_lshade", score_index)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    "weights",
    [
        [],
        [1.0],
        [1.0] + [0.0] * 6,
        [-0.1, 1.1, 0, 0, 0, 0],
        [float("nan")] + [0.0] * 5,
        [float("inf")] + [0.0] * 5,
        [0.0] * 6,
        [0.16] * 6,
        [0.2] * 6,
    ],
)
def test_invalid_move_weights_raise_value_error(algorithm, weights):
    manager = variables_manager([variable(initial=index + 1) for index in range(7)])
    with pytest.raises(ValueError, match="(?i)(weight|proba|sum|move)"):
        make_method(algorithm, manager, weights=weights)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_high_level_agents_preserve_an_explicit_empty_move_portfolio(algorithm):
    common = {
        "termination_strategy": StepsLimit(2),
        "tabu_entity_rate": 0.0,
        "move_probas": [],
    }
    if algorithm == "tabu":
        agent = TabuSearch(neighbours_count=4, **common)
    elif algorithm == "late":
        agent = LateAcceptance(late_acceptance_size=4, **common)
    elif algorithm == "annealing":
        agent = SimulatedAnnealing(
            initial_temperature=[1.0], cooling_rate=0.99, **common
        )
    elif algorithm == "genetic":
        agent = GeneticAlgorithm(population_size=8, p_best_rate=0.5, **common)
    else:
        agent = LSHADE(
            population_size=8, history_archive_size=8, p_best_rate=0.5, **common
        )
    calculator = PlainScoreCalculator()
    calculator.score_variant = ScoreVariants.SimpleScore
    cotwin = CotwinBase()
    cotwin.add_planning_entities_list(
        [SimpleNamespace(id=0, value=GJInteger(0, 10, False, initial_value=5))], "items"
    )
    cotwin.set_score_calculator(calculator)
    agent.cotwin = cotwin
    with pytest.raises(ValueError, match="(?i)(weight|proba|sum|move)"):
        agent._build_metaheuristic_base()


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    "option,value",
    [
        ("tabu_rate", -0.01),
        ("tabu_rate", 1.01),
        ("tabu_rate", float("nan")),
        ("tabu_rate", float("inf")),
        ("multiplier", -0.01),
        ("multiplier", float("nan")),
        ("multiplier", float("inf")),
    ],
)
def test_invalid_mutation_configuration_raises_value_error(algorithm, option, value):
    manager = variables_manager([variable(initial=index + 1) for index in range(7)])
    with pytest.raises(ValueError, match="(?i)(tabu|mutation|multiplier|finite|rate)"):
        make_method(algorithm, manager, **{option: value})


@pytest.mark.parametrize(
    "options",
    [
        {"lower": float("nan")},
        {"upper": float("nan")},
        {"lower": float("-inf")},
        {"upper": float("inf")},
        {"lower": -1e308, "upper": 1e308, "integer": False},
        {"lower": 21, "upper": 20},
        {"initial": -1},
        {"initial": 21},
        {"initial": float("nan")},
        {"initial": float("inf")},
        {"frozen": True},
        {"lower": 0.5},
        {"upper": 20.5},
        {"initial": 1.5},
    ],
)
def test_invalid_variable_bounds_and_initialization_fail_early(options):
    with pytest.raises(ValueError):
        variable(**options)


@pytest.mark.parametrize("integer,bound", [(True, -3), (False, 2.75)])
def test_fixed_ranges_sample_and_project_to_the_single_bound(integer, bound):
    manager = variables_manager([variable(bound, bound, integer=integer)])
    for _ in range(20):
        assert manager.sample_variables() == [bound]
        assert manager.get_column_random_value(0) == bound
    assert manager.fix_variables([bound - 10], None) == [bound]
    assert manager.fix_variables([bound + 10], None) == [bound]


def test_frozen_initialized_variables_keep_their_value_when_sampled_or_projected():
    manager = variables_manager(
        [variable(-4.5, 7.25, integer=False, initial=1.125, frozen=True)]
    )
    for _ in range(20):
        assert manager.sample_variables() == [1.125]
    assert manager.fix_variables([-100], None) == [1.125]
    assert manager.fix_variables([100], None) == [1.125]


if __name__ == "__main__":
    case, *arguments = sys.argv[1:]
    if case == "operator":
        operator_contract(*map(int, arguments))
    elif case == "default":
        default_portfolio_contract(int(arguments[0]))
    elif case == "mixed":
        mixed_groups_contract(int(arguments[0]))
    elif case == "ineligible":
        no_eligible_contract(arguments[0])
    elif case == "disjoint_groups":
        disjoint_groups_contract()
    elif case == "identical_lshade":
        identical_lshade_contract(int(arguments[0]))
    else:
        raise AssertionError(f"Unknown move contract case: {case}")
    print(json.dumps({"case": case, "passed": True}))
