"""Regression tests for the original GreyJack employee scheduling example."""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

# The examples are checkout files, while greyjack must remain the installed wheel.
# Add only the repository root, never its greyjack source-package directory.
sys.path.append(str(Path(__file__).resolve().parents[3]))

from examples.object_oriented.employee_scheduling.domain.Employee import Employee
from examples.object_oriented.employee_scheduling.domain.EmployeeSchedule import (
    EmployeeSchedule,
)
from examples.object_oriented.employee_scheduling.domain.Shift import Shift
from examples.object_oriented.employee_scheduling.persistence.CotwinBuilder import (
    CotwinBuilder,
)
from examples.object_oriented.employee_scheduling.score.IncrementalScoreCalculator import (
    compute_penalties,
)


DAY = date(2026, 9, 28)
START = datetime(2026, 9, 28, 22)


def make_shift(shift_id, start, end):
    return Shift(shift_id, start, end, "Ward", "Nurse")


def make_cotwin(shifts, employees=None):
    if employees is None:
        employees = [Employee("A", ["Nurse"])]
    domain = EmployeeSchedule(employees, shifts)
    return CotwinBuilder(True, False).build_cotwin(domain, False)


def score_utilities(cotwin, assignments, delta_rows=(), delta_values=()):
    utilities = cotwin.score_calculator.utility_objects
    return compute_penalties(
        utilities["shift_starts"],
        utilities["shift_ends"],
        utilities["shift_start_dates"],
        utilities["shift_req_skills"],
        utilities["employee_skills"],
        utilities["employee_unavailable_dates"],
        utilities["employee_undesired_dates"],
        utilities["employee_desired_dates"],
        len(assignments),
        np.array(assignments, dtype=np.int64),
        np.array(delta_rows, dtype=np.int64),
        np.array(delta_values, dtype=np.int64),
    )


def test_cotwin_utilities_store_actual_end_and_start_calendar_date():
    end = START + timedelta(hours=8)
    cotwin = make_cotwin([make_shift(17, START, end)])
    utility = cotwin.score_calculator.utility_objects
    assert utility["shift_starts"] == [int(START.timestamp() // 60)]
    assert utility["shift_ends"] == [int(end.timestamp() // 60)]
    midnight = datetime.combine(DAY, datetime.min.time())
    assert utility["shift_start_dates"] == [int(midnight.timestamp() // 60)]
    assert utility["shift_ends"][0] - utility["shift_starts"][0] == 480
    assert utility["shift_start_dates"] != utility["shift_starts"]


@pytest.mark.parametrize(
    ("second_start", "expected_overlap", "expected_rest", "expected_same_day"),
    [
        (START + timedelta(hours=1), 840, 0, 2),
        (START + timedelta(hours=8), 0, 1200, 0),
        (START + timedelta(hours=18, minutes=-1), 0, 2, 0),
        (START + timedelta(hours=18), 0, 0, 0),
        (START + timedelta(hours=18, minutes=1), 0, 0, 0),
    ],
)
def test_overlap_rest_threshold_and_same_start_date(
    second_start, expected_overlap, expected_rest, expected_same_day
):
    cotwin = make_cotwin(
        [
            make_shift(17, START, START + timedelta(hours=8)),
            make_shift(42, second_start, second_start + timedelta(hours=8)),
        ]
    )
    # Expected values are computed by hand; ordered pairs count each penalty twice.
    assert score_utilities(cotwin, [0, 0]) == (
        0,
        0,
        expected_overlap,
        expected_rest,
        expected_same_day,
        0,
        0,
        0,
    )


def test_preferences_and_unavailability_use_start_date_for_overnight_shift():
    employee = Employee("A", ["Doctor"])
    employee.unavailable_dates = [DAY]
    employee.undesired_dates = [DAY]
    employee.desired_dates = [DAY + timedelta(days=1)]
    shift = make_shift(17, START, START + timedelta(hours=8))
    cotwin = make_cotwin([shift], [employee])
    assert score_utilities(cotwin, [0]) == (1, 1, 0, 0, 0, 1, 0, 0)

    employee.unavailable_dates = [DAY + timedelta(days=1)]
    employee.undesired_dates = [DAY + timedelta(days=1)]
    employee.desired_dates = [DAY]
    cotwin = make_cotwin([shift], [employee])
    assert score_utilities(cotwin, [0]) == (1, 0, 0, 0, 0, 0, -1, 0)


def test_delta_reassignment_removes_pair_penalties_and_balances_workload():
    cotwin = make_cotwin(
        [
            make_shift(17, START, START + timedelta(hours=8)),
            make_shift(42, START, START + timedelta(hours=8)),
        ],
        [Employee("A", ["Nurse"]), Employee("B", ["Nurse"])],
    )
    assert score_utilities(cotwin, [0, 0], [1], [1]) == (0,) * 8


@pytest.mark.parametrize("already_initialized,greedy", [(True, False), (False, True)])
def test_builder_construction_errors_reach_caller(already_initialized, greedy):
    domain = EmployeeSchedule([Employee("A", ["Nurse"])], [])
    with pytest.raises(Exception, match="not already implemented"):
        CotwinBuilder(True, greedy).build_cotwin(domain, already_initialized)
