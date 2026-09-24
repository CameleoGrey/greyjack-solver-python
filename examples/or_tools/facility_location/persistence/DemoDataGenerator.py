from .DemoDataBuilder import DemoDataBuilder
from ..domain.Location import Location


class DemoDataGenerator:
    def __init__(self, seed: int = 0):
        self.seed = seed

    def generate_demo_data(self):
        return (
            DemoDataBuilder.builder()
            .set_capacity(4500)
            .set_demand(900)
            .set_facility_count(30)
            .set_consumer_count(60)
            .set_south_west_corner(Location(51.44, -0.16))
            .set_north_east_corner(Location(51.56, -0.01))
            .set_average_setup_cost(50_000)
            .set_setup_cost_standard_deviation(10_000)
            .build(seed=self.seed)
        )
