"""A candidate must compose every changed field on an affected business row."""

from copy import deepcopy

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from greyjack.greyjack import CandidateDfsBuilderPy
from greyjack.variables.GJFloat import GJFloat
from greyjack.variables.GJInteger import GJInteger


def make_builder(groups, *, integer_y=False):
    variables = []
    names = {}
    slots = []
    planning = {}
    for group_name, entity_ids in groups.items():
        planning[group_name] = pl.DataFrame(
            {
                "sample_id": [0] * len(entity_ids),
                "entity_id": entity_ids,
                "label": [f"{group_name}-{row}" for row in range(len(entity_ids))],
                "x": [None] * len(entity_ids),
                "y": [None] * len(entity_ids),
            }
        )
        for row in range(len(entity_ids)):
            for column in ("x", "y"):
                variable_type = GJInteger if column == "x" or integer_y else GJFloat
                variable = variable_type(-100, 100, False).planning_variable
                variable.name = f"{group_name}: {len(variables)}-->{column}"
                names[variable.name] = len(variables)
                variables.append(variable)
                slots.append((group_name, row, column))
    facts = pl.DataFrame({"name": ["unchanged"], "cost": [17]})
    builder = CandidateDfsBuilderPy(
        variables,
        names,
        {index: name for name, index in names.items()},
        {name: ["entity_id", "label", "x", "y"] for name in groups},
        {"facts": facts.columns},
        planning,
        {"facts": facts},
        {"entity_id": True, "x": True, "y": integer_y},
    )
    return builder, slots, facts


@pytest.mark.parametrize(
    "changes,expected",
    [
        ([(0, 5), (1, 6)], (0, 0, 5, 6)),
        ([(1, 6), (0, 5)], (0, 0, 5, 6)),
        ([(0, 5), (1, 6), (0, 9)], (0, 0, 9, 6)),
    ],
)
def test_two_changed_variables_form_one_complete_entity_row(changes, expected):
    builder, _, _ = make_builder({"items": [901]}, integer_y=True)
    baseline, _, deltas = builder.get_incremental_candidate_dfs([1, 2], [changes])
    assert baseline["items"].select("entity_id", "x", "y").rows() == [(901, 1, 2)]
    assert deltas["items"].select(
        "sample_id", "candidate_df_row_id", "x", "y"
    ).rows() == [expected]
    assert all(dtype == pl.Int64 for dtype in deltas["items"].schema.values())


def expected_domain(groups, slots, values):
    result = {
        name: [
            {"entity_id": entity_id, "label": f"{name}-{row}"}
            for row, entity_id in enumerate(entity_ids)
        ]
        for name, entity_ids in groups.items()
    }
    for (name, row, column), value in zip(slots, values):
        result[name][row][column] = int(value) if column == "x" else value
    return result


def score(domain):
    """Cross-field interactions reveal lost assignments; quarters are exact floats."""
    hard = sum(row["x"] > row["y"] for rows in domain.values() for row in rows)
    soft = sum(
        (group_index + 1) * ((row_index + 1) * row["x"] * row["y"] + row["x"] ** 2)
        for group_index, name in enumerate(sorted(domain))
        for row_index, row in enumerate(domain[name])
    )
    return hard, soft


@pytest.mark.parametrize("prime_with_plain", [False, True])
def test_full_candidates_and_composed_delta_rows_have_identical_assignments_and_scores(
    prime_with_plain,
):
    groups = {"items": [901, -17, 44], "crews": [800, 12], "idle": [-300]}
    builder, slots, facts = make_builder(groups)
    baseline = [1, 2.5, 3, 4.5, 5, 6.5, 7, 8.5, 9, 10.5, 11, 12.5]
    if prime_with_plain:
        builder.get_plain_candidate_dfs([baseline, baseline])
        baseline = [value + 1 for value in baseline]
    changes = [
        [(3, 14.25), (2, 13), (0, 21), (1, 22.5)],
        [(9, 18.75), (7, 16.25), (8, 19), (6, 17), (4, 25)],
        [(0, 31), (0, 32), (3, 34.5), (7, 36.25), (6, 37), (7, 38.75)],
        [(4, 45), (8, 49)],
        [(2, baseline[2]), (3, baseline[3])],
    ]
    candidates = []
    for assignments in changes:
        candidate = baseline.copy()
        for variable_id, value in assignments:
            candidate[variable_id] = value
        candidates.append(candidate)

    native, returned_facts, deltas = builder.get_incremental_candidate_dfs(
        baseline, changes
    )
    assert_frame_equal(returned_facts["facts"], facts)
    assert "idle" not in deltas
    before = expected_domain(groups, slots, baseline)
    actual_baseline = {
        name: frame.select("entity_id", "label", "x", "y").to_dicts()
        for name, frame in native.items()
    }
    assert actual_baseline == before
    for name, frame in deltas.items():
        assert frame.schema == {
            "sample_id": pl.Int64,
            "candidate_df_row_id": pl.Int64,
            "x": pl.Int64,
            "y": pl.Float64,
        }
        keys = frame.select("sample_id", "candidate_df_row_id").rows()
        assert keys == sorted(set(keys))
        expected_keys = {
            (sample_id, slots[variable_id][1])
            for sample_id, assignments in enumerate(changes)
            for variable_id, _ in assignments
            if slots[variable_id][0] == name
        }
        assert set(keys) == expected_keys

    plain_builder, _, _ = make_builder(groups)
    plain, plain_facts = plain_builder.get_plain_candidate_dfs(candidates)
    assert_frame_equal(plain_facts["facts"], facts)
    for sample_id, candidate in enumerate(candidates):
        expected = expected_domain(groups, slots, candidate)
        reconstructed = deepcopy(actual_baseline)
        for name, frame in deltas.items():
            for row in frame.filter(pl.col("sample_id") == sample_id).to_dicts():
                target = reconstructed[name][row["candidate_df_row_id"]]
                target.update({"x": row["x"], "y": row["y"]})
        full_plain = {
            name: frame.filter(pl.col("sample_id") == sample_id)
            .select("entity_id", "label", "x", "y")
            .to_dicts()
            for name, frame in plain.items()
        }
        assert reconstructed == full_plain == expected
        assert score(reconstructed) == score(full_plain) == score(expected)
    assert actual_baseline == before

    # Reuse the same builder with a different baseline: untouched fields must
    # come from this request, rather than a prior candidate or a prior request.
    new_baseline = [value + 2 for value in baseline]
    later_native, _, later_deltas = builder.get_incremental_candidate_dfs(
        new_baseline, [[(1, 55.25), (0, 54), (1, 56.5)], [(10, 60)]]
    )
    assert later_deltas["items"].select(
        "sample_id", "candidate_df_row_id", "x", "y"
    ).rows() == [(0, 0, 54, 56.5)]
    assert later_deltas["idle"].select(
        "sample_id", "candidate_df_row_id", "x", "y"
    ).rows() == [(1, 0, 60, new_baseline[11])]
    assert later_native["crews"]["y"].to_list() == [new_baseline[7], new_baseline[9]]
