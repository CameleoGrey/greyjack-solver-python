import random
from itertools import count

from examples.object_oriented.facility_location.domain import *

class DemoDataBuilder:
    _sequence = count(1)

    def __init__(self):
        self.capacity = 0
        self.demand = 0
        self.facility_count = 0
        self.consumer_count = 0
        self.average_setup_cost = 0
        self.setup_cost_standard_deviation = 0
        self.south_west_corner = None
        self.north_east_corner = None

    @staticmethod
    def builder():
        return DemoDataBuilder()

    def set_capacity(self, capacity):
        self.capacity = capacity
        return self

    def set_demand(self, demand):
        self.demand = demand
        return self

    def set_facility_count(self, facility_count):
        self.facility_count = facility_count
        return self

    def set_consumer_count(self, consumer_count):
        self.consumer_count = consumer_count
        return self

    def set_average_setup_cost(self, average_setup_cost):
        self.average_setup_cost = average_setup_cost
        return self

    def set_setup_cost_standard_deviation(self, setup_cost_standard_deviation):
        self.setup_cost_standard_deviation = setup_cost_standard_deviation
        return self

    def set_south_west_corner(self, south_west_corner):
        self.south_west_corner = south_west_corner
        return self

    def set_north_east_corner(self, north_east_corner):
        self.north_east_corner = north_east_corner
        return self

    def build(self):
        if self.demand < 1:
            raise ValueError(f"Demand ({self.demand}) must be greater than zero.")
        if self.capacity < 1:
            raise ValueError(f"Capacity ({self.capacity}) must be greater than zero.")
        if self.facility_count < 1:
            raise ValueError(f"Number of facilities ({self.facility_count}) must be greater than zero.")
        if self.consumer_count < 1:
            raise ValueError(f"Number of consumers ({self.consumer_count}) must be greater than zero.")
        if self.demand > self.capacity:
            raise ValueError(f"Overconstrained problem not supported. The total capacity ({self.capacity}) must be greater than or equal to the total demand ({self.demand}).")

        random.seed(0)
        
        def location_supplier():
            lat = random.uniform(self.south_west_corner.latitude, self.north_east_corner.latitude)
            lon = random.uniform(self.south_west_corner.longitude, self.north_east_corner.longitude)
            return Location(lat, lon)
        
        facilities = []
        for i, _ in enumerate(range(self.facility_count)):
            location = location_supplier()
            setup_cost = self.average_setup_cost + int(self.setup_cost_standard_deviation * random.gauss(0, 1))
            capacity = self.capacity // self.facility_count
            facilities.append(Facility(i, location, setup_cost, capacity))
        
        consumers = []
        for i, _ in enumerate(range(self.consumer_count)):
            location = location_supplier()
            demand = self.demand // self.consumer_count
            consumers.append(Consumer(i, location, demand))
        
        return FacilityLocationDomain(facilities, consumers, self.south_west_corner, self.north_east_corner)