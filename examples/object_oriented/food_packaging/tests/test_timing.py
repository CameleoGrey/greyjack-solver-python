import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np

from examples.object_oriented.food_packaging.domain import (
    Line,
    PackagingSchedule,
    Product,
)
from examples.object_oriented.food_packaging.persistence.CotwinBuilder import (
    CotwinBuilder,
)
from examples.object_oriented.food_packaging.score.IncrementalScoreCalculator import (
    compute_penalties,
)


def int_array(values):
    return np.asarray(values, dtype=np.int64)


def score(
    *,
    products,
    durations,
    ideal_ends,
    max_ends,
    priorities,
    operators,
    line_starts,
    cleaning,
    assigned_lines,
    positions,
):
    count = len(products)
    empty = int_array([])
    return compute_penalties(
        int_array(products),
        int_array(durations),
        int_array([0] * count),
        int_array(ideal_ends),
        int_array(max_ends),
        int_array(priorities),
        int_array(operators),
        int_array(line_starts),
        len(line_starts),
        np.asarray(cleaning, dtype=np.int64),
        int_array(range(count)),
        int_array(assigned_lines),
        int_array(positions),
        empty,
        empty,
        empty,
    )


class OriginalFoodPackagingTimingTests(unittest.TestCase):
    def test_first_job_has_real_end_for_deadlines_and_makespan(self):
        result = score(
            products=[0],
            durations=[60],
            ideal_ends=[45],
            max_ends=[30],
            priorities=[1],
            operators=[0],
            line_starts=[0],
            cleaning=[[0]],
            assigned_lines=[0],
            positions=[0],
        )
        self.assertEqual(result, (0, 30, 15, 0, 3600, 0))

    def test_incoming_product_is_cleaned_before_production(self):
        result = score(
            products=[0, 1],
            durations=[10, 10],
            ideal_ends=[10, 35],
            max_ends=[10, 35],
            priorities=[1, 3],
            operators=[0],
            line_starts=[0],
            cleaning=[[0, 0], [20, 0]],
            assigned_lines=[0, 0],
            positions=[0, 1],
        )
        # A: [0,10), clean B after A: [10,30), B: [30,40).
        self.assertEqual(result, (0, 5, 5, 0, 40**2, 3 * 20))

    def test_same_operator_production_overlap_uses_first_job_end(self):
        result = score(
            products=[0, 0],
            durations=[60, 60],
            ideal_ends=[60, 60],
            max_ends=[60, 60],
            priorities=[1, 1],
            operators=[0, 0],
            line_starts=[0, 0],
            cleaning=[[0]],
            assigned_lines=[0, 1],
            positions=[0, 0],
        )
        self.assertEqual(result, (0, 0, 0, 60, 2 * 60**2, 0))

    def test_position_collision_penalty_is_preserved(self):
        result = score(
            products=[0, 0],
            durations=[10, 10],
            ideal_ends=[100, 100],
            max_ends=[100, 100],
            priorities=[1, 1],
            operators=[0],
            line_starts=[0],
            cleaning=[[0]],
            assigned_lines=[0, 0],
            positions=[0, 0],
        )
        self.assertEqual(result[0], 100_000)

    def test_cotwin_uses_full_wall_clock_times_and_timedeltas(self):
        product = Product(0, "P")
        product.cleaning_durations[product] = timedelta(hours=25)
        line_start = datetime(2026, 9, 28, 8, 30)
        ideal_end = datetime(2026, 9, 28, 9, 15)
        max_end = datetime(2026, 9, 28, 9, 20)
        domain = PackagingSchedule()
        domain.products = [product]
        domain.lines = [Line(0, "L", "Operator A", line_start)]
        planning_job = SimpleNamespace(
            product_id=0,
            duration=timedelta(hours=26, minutes=30),
            min_start_time=datetime(2026, 9, 28, 8, 45),
            ideal_end_time=ideal_end,
            max_end_time=max_end,
            priority=1,
        )
        calculator = SimpleNamespace(utility_objects={})
        CotwinBuilder(True, False)._add_utility_info_for_incremental_scoring(
            domain, calculator, [planning_job]
        )
        facts = calculator.utility_objects
        self.assertEqual(facts["durations"], [26 * 60 + 30])
        self.assertEqual(facts["ideal_end_times"][0] - facts["start_date_times"][0], 45)
        self.assertEqual(facts["max_end_times"][0] - facts["start_date_times"][0], 50)
        self.assertEqual(facts["min_start_times"][0] - facts["start_date_times"][0], 15)
        self.assertEqual(facts["cleaning_duration_matrix"][0, 0], 25 * 60)


if __name__ == "__main__":
    unittest.main()
