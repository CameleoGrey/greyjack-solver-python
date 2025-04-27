
from .DemoDataBuilder import DemoDataBuilder
from examples.object_oriented.facility_location.domain import *

class DemoDataGenerator:

    def __init__(self):
        pass

    def generate_demo_data(self):
        problem = DemoDataBuilder.builder() \
            .set_capacity(4500) \
            .set_demand(900) \
            .set_facility_count(30) \
            .set_consumer_count(60) \
            .set_south_west_corner(Location(51.44, -0.16)) \
            .set_north_east_corner(Location(51.56, -0.01)) \
            .set_average_setup_cost(50000) \
            .set_setup_cost_standard_deviation(10000) \
            .build()
        
        return problem