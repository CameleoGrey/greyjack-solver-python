"""Exercise the native DataFrame boundary through real candidate generation."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from greyjack.agents import (
    GeneticAlgorithm,
    LSHADE,
    LateAcceptance,
    SimulatedAnnealing,
    TabuSearch,
)
from greyjack.agents.termination_strategies.StepsLimit import StepsLimit
from greyjack.cotwin.CotwinBase import CotwinBase
from greyjack.greyjack import CandidateDfsBuilderPy
from greyjack.score_calculation.score_calculators.PlainScoreCalculator import (
    PlainScoreCalculator,
)
from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.variables.GJInteger import GJInteger


def candidate_builder(facts):
    variables = []
    names = {}
    for index in range(2):
        variable = GJInteger(0, 10, False).planning_variable
        variable.name = f"shifts: {index}-->employee_id"
        names[variable.name] = index
        variables.append(variable)
    return CandidateDfsBuilderPy(
        variables,
        names,
        {index: name for name, index in names.items()},
        {"shifts": ["shift_id", "employee_id"]},
        {"facts": facts.columns},
        {
            "shifts": pl.DataFrame(
                {
                    "sample_id": [0, 0],
                    "shift_id": [901, -17],
                    "employee_id": [None, None],
                }
            )
        },
        {"facts": facts},
        {"shift_id": True, "employee_id": True},
    )


def heterogeneous_facts():
    return pl.DataFrame(
        {
            "integer": pl.Series([2**53 + 1, None], dtype=pl.Int64),
            "float": [1.25, None],
            "text": ["Ward α", None],
            "flag": [True, False],
            "day": [date(2026, 9, 28), None],
            "instant": [datetime(2026, 9, 28, 6), None],
            "duration": [timedelta(minutes=37), None],
            "null": [None, None],
            "list": [[1, 2], []],
        }
    )


@pytest.mark.parametrize("shape", ["normal", "empty", "chunked"])
def test_round_trip_preserves_business_values_schema_and_chunks(shape):
    facts = heterogeneous_facts()
    if shape == "empty":
        facts = facts.head(0)
    elif shape == "chunked":
        facts = pl.concat([facts, facts], rechunk=False)
        assert facts["integer"].n_chunks() > 1
    before = facts.clone()
    builder = candidate_builder(facts)
    planning, returned_facts = builder.get_plain_candidate_dfs([[2, 5], [7, 9]])
    assert_frame_equal(returned_facts["facts"], before)
    assert_frame_equal(facts, before)
    assert planning["shifts"].select("sample_id", "shift_id", "employee_id").rows() == [
        (0, 901, 2),
        (0, -17, 5),
        (1, 901, 7),
        (1, -17, 9),
    ]
    assert planning["shifts"].schema["employee_id"] == pl.Int64


def test_incremental_candidates_preserve_native_row_mapping_and_facts():
    facts = heterogeneous_facts()
    builder = candidate_builder(facts)
    planning, returned_facts, deltas = builder.get_incremental_candidate_dfs(
        [2, 5], [[(1, 8)], [(0, 9), (1, 3)]]
    )
    assert_frame_equal(returned_facts["facts"], facts)
    assert planning["shifts"].select(
        "candidate_df_row_id", "shift_id", "employee_id"
    ).rows() == [(0, 901, 2), (1, -17, 5)]
    assert deltas["shifts"].select(
        "sample_id", "candidate_df_row_id", "employee_id"
    ).rows() == [(0, 1, 8), (1, 0, 9), (1, 1, 3)]
    assert deltas["shifts"].schema == {
        name: pl.Int64 for name in deltas["shifts"].columns
    }
    # A later request must replace the previous sample and row identifiers.
    planning, _, deltas = builder.get_incremental_candidate_dfs([4, 6], [[(0, 1)]])
    assert planning["shifts"]["employee_id"].to_list() == [4, 6]
    assert deltas["shifts"].select(
        "sample_id", "candidate_df_row_id", "employee_id"
    ).rows() == [(0, 0, 1)]


SCORES = [
    (ScoreVariants.SimpleScore, SimpleScore, 1),
    (ScoreVariants.HardSoftScore, HardSoftScore, 2),
    (ScoreVariants.HardMediumSoftScore, HardMediumSoftScore, 3),
]


@pytest.mark.parametrize("variant,score_type,levels", SCORES)
@pytest.mark.parametrize(
    "algorithm", ["tabu", "genetic", "late", "annealing", "lshade"]
)
def test_all_native_search_bindings_score_and_step(
    variant, score_type, levels, algorithm
):
    termination = StepsLimit(2)
    common = {
        "termination_strategy": termination,
        "tabu_entity_rate": 0.0,
        "move_probas": [0.5, 0.5, 0, 0, 0, 0],
    }
    if algorithm == "tabu":
        agent = TabuSearch(neighbours_count=4, **common)
    elif algorithm == "genetic":
        agent = GeneticAlgorithm(population_size=8, p_best_rate=0.5, **common)
    elif algorithm == "late":
        agent = LateAcceptance(late_acceptance_size=4, **common)
    elif algorithm == "annealing":
        agent = SimulatedAnnealing(
            initial_temperature=[1.0] * levels, cooling_rate=0.99, **common
        )
    else:
        agent = LSHADE(
            population_size=8, history_archive_size=8, p_best_rate=0.5, **common
        )

    calculator = PlainScoreCalculator()
    calculator.score_variant = variant

    def score_candidates(planning, facts):
        totals = (
            planning["items"]
            .group_by("sample_id")
            .agg(pl.col("value").sum())
            .sort("sample_id")
        )
        return [
            score_type(*([0] * (levels - 1) + [float(value)]))
            for value in totals["value"]
        ]

    calculator.add_constraint("sum", score_candidates)
    cotwin = CotwinBase()
    cotwin.add_planning_entities_list(
        [SimpleNamespace(id=i, value=GJInteger(0, 10, False)) for i in range(4)],
        "items",
    )
    cotwin.set_score_calculator(calculator)
    agent.cotwin = cotwin
    agent.score_precision = [0] * levels
    agent._define_individual_type()
    agent._build_metaheuristic_base()
    agent._init_population()
    agent.population.sort()
    agent.agent_top_individual = agent.population[0].copy()
    agent._step_plain()
    assert agent.population
    for candidate in agent.population:
        assert candidate.score.as_list() == [0] * (levels - 1) + [
            sum(candidate.variable_values)
        ]
        assert all(
            0 <= value <= 10 and int(value) == value
            for value in candidate.variable_values
        )
