"""Port of the Timefold-derived source generator (Apache License 2.0).

Source and license notice:
examples/object_oriented/food_packaging/persistence/DemoDataGenerator.py
https://www.apache.org/licenses/LICENSE-2.0
"""

from datetime import date, datetime, time, timedelta
from random import Random

from ..domain import Job, Line, PackagingSchedule, Product


class DemoDataGenerator:
    INGREDIENT_LIST = (
        "Carrots",
        "Peas",
        "Cabbage",
        "Tomato",
        "Eggplant",
        "Broccoli",
        "Spinach",
        "Pumpkin",
        "Pepper",
        "Onions",
    )
    PRODUCT_VARIATION_LIST = ("small bag", "medium bag", "large bag")

    def __init__(
        self,
        line_count: int = 5,
        job_count: int = 100,
        *,
        seed: int = 37,
        start_date: date | None = None,
    ):
        if type(line_count) is not int or line_count < 1:
            raise ValueError("line_count must be a positive integer")
        if type(job_count) is not int or job_count < 0:
            raise ValueError("job_count must be a nonnegative integer")
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        if start_date is not None and (
            not isinstance(start_date, date) or isinstance(start_date, datetime)
        ):
            raise ValueError("start_date must be a date-only value")
        self.line_count = line_count
        self.job_count = job_count
        self.seed = seed
        self.start_date = start_date or self.next_monday(date.today())

    @staticmethod
    def next_monday(today: date) -> date:
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)

    def generate_demo_data(self) -> PackagingSchedule:
        no_cleaning_minutes = 10
        cleaning_minutes_minimum = 30
        cleaning_minutes_maximum = 60
        job_duration_minutes_minimum = 120
        job_duration_minutes_maximum = 300
        average_cleaning_and_job_duration_minutes = (
            2 * no_cleaning_minutes
            + cleaning_minutes_minimum
            + cleaning_minutes_maximum
        ) // 4 + (job_duration_minutes_minimum + job_duration_minutes_maximum) // 2
        start_date_time = datetime.combine(self.start_date, time.min)
        rng = Random(self.seed)
        ingredient_map: dict[Product, set[str]] = {}
        product_id = 0
        for i, ingredient in enumerate(self.INGREDIENT_LIST):
            offset = rng.randint(0, len(self.INGREDIENT_LIST) - 5)
            ingredient_a = self.INGREDIENT_LIST[(i + offset + 1) % 10]
            ingredient_b = self.INGREDIENT_LIST[(i + offset + 2) % 10]
            ingredient_c = self.INGREDIENT_LIST[(i + offset + 3) % 10]
            for variation in self.PRODUCT_VARIATION_LIST:
                ingredient_map[Product(product_id, f"{ingredient} {variation}")] = {
                    ingredient
                }
                product_id += 1
            ingredient_map[
                Product(
                    product_id,
                    f"{ingredient} and {ingredient_a} {self.PRODUCT_VARIATION_LIST[1]}",
                )
            ] = {ingredient, ingredient_a}
            product_id += 1
            ingredient_map[
                Product(
                    product_id,
                    f"{ingredient} and {ingredient_b} {self.PRODUCT_VARIATION_LIST[2]}",
                )
            ] = {ingredient, ingredient_b}
            product_id += 1
            ingredient_map[
                Product(
                    product_id,
                    f"{ingredient}, {ingredient_a} and {ingredient_c} "
                    f"{self.PRODUCT_VARIATION_LIST[1]}",
                )
            ] = {ingredient, ingredient_a, ingredient_c}
            product_id += 1

        products = list(ingredient_map)
        for product in products:
            ingredients = ingredient_map[product]
            for previous in products:
                no_cleaning = ingredients.issuperset(ingredient_map[previous])
                if product is previous:
                    cleaning_minutes = 0
                elif no_cleaning:
                    cleaning_minutes = no_cleaning_minutes
                else:
                    cleaning_minutes = cleaning_minutes_minimum + rng.randint(
                        0, cleaning_minutes_maximum - cleaning_minutes_minimum
                    )
                product.cleaning_durations[previous] = timedelta(
                    minutes=cleaning_minutes
                )

        lines = [
            Line(
                i,
                f"Line {i + 1}",
                f"Operator {chr(ord('A') + i // 2)}",
                start_date_time,
            )
            for i in range(self.line_count)
        ]
        jobs = []
        for i in range(self.job_count):
            product = rng.choice(products)
            duration = timedelta(
                minutes=job_duration_minutes_minimum
                + rng.randint(
                    0, job_duration_minutes_maximum - job_duration_minutes_minimum
                )
            )
            target_day_index = (
                (i // self.line_count)
                * average_cleaning_and_job_duration_minutes
                // (24 * 60)
            )
            min_start = datetime.combine(
                self.start_date
                + timedelta(days=rng.randint(0, max(0, target_day_index - 2))),
                time.min,
            )
            ideal_end = datetime.combine(
                self.start_date + timedelta(days=target_day_index + rng.randint(0, 2)),
                time(16, 0),
            )
            max_end = ideal_end + timedelta(days=1 + rng.randint(0, 2))
            jobs.append(
                Job(
                    i,
                    product.name,
                    product,
                    duration,
                    min_start,
                    ideal_end,
                    max_end,
                    1,
                    False,
                )
            )
        schedule = PackagingSchedule(products, lines, jobs)
        schedule.validate()
        return schedule
