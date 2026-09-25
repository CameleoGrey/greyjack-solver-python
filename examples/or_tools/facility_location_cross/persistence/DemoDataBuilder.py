import random

from ..domain import Consumer, Facility, FacilityLocationDomain, Location


class DemoDataBuilder:
    """Generate the original example's uniformly sized facilities and consumers."""

    def __init__(self):
        self.capacity = 0
        self.demand = 0
        self.facility_count = 0
        self.consumer_count = 0
        self.average_setup_cost = 0
        self.setup_cost_standard_deviation = 0
        self.south_west_corner: Location | None = None
        self.north_east_corner: Location | None = None

    @staticmethod
    def builder() -> "DemoDataBuilder":
        return DemoDataBuilder()

    def set_capacity(self, capacity: int) -> "DemoDataBuilder":
        self.capacity = capacity
        return self

    def set_demand(self, demand: int) -> "DemoDataBuilder":
        self.demand = demand
        return self

    def set_facility_count(self, facility_count: int) -> "DemoDataBuilder":
        self.facility_count = facility_count
        return self

    def set_consumer_count(self, consumer_count: int) -> "DemoDataBuilder":
        self.consumer_count = consumer_count
        return self

    def set_average_setup_cost(self, average_setup_cost: int) -> "DemoDataBuilder":
        self.average_setup_cost = average_setup_cost
        return self

    def set_setup_cost_standard_deviation(
        self, standard_deviation: int
    ) -> "DemoDataBuilder":
        self.setup_cost_standard_deviation = standard_deviation
        return self

    def set_south_west_corner(self, corner: Location) -> "DemoDataBuilder":
        self.south_west_corner = corner
        return self

    def set_north_east_corner(self, corner: Location) -> "DemoDataBuilder":
        self.north_east_corner = corner
        return self

    def build(self, seed: int = 0) -> FacilityLocationDomain:
        for name in ("capacity", "demand", "facility_count", "consumer_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.demand > self.capacity:
            raise ValueError("Total demand exceeds total capacity")
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        if type(self.average_setup_cost) is not int:
            raise ValueError("average_setup_cost must be an integer")
        if (
            type(self.setup_cost_standard_deviation) is not int
            or self.setup_cost_standard_deviation < 0
        ):
            raise ValueError("setup_cost_standard_deviation must be nonnegative")
        if not isinstance(self.south_west_corner, Location) or not isinstance(
            self.north_east_corner, Location
        ):
            raise ValueError("Both geographic corners are required")
        self.south_west_corner.validate()
        self.north_east_corner.validate()
        if (
            self.south_west_corner.latitude > self.north_east_corner.latitude
            or self.south_west_corner.longitude > self.north_east_corner.longitude
        ):
            raise ValueError("South-west corner must precede north-east corner")

        rng = random.Random(seed)

        def next_location() -> Location:
            return Location(
                rng.uniform(
                    self.south_west_corner.latitude, self.north_east_corner.latitude
                ),
                rng.uniform(
                    self.south_west_corner.longitude, self.north_east_corner.longitude
                ),
            )

        facilities = [
            Facility(
                id=index,
                location=next_location(),
                setup_cost=self.average_setup_cost
                + int(self.setup_cost_standard_deviation * rng.gauss(0, 1)),
                capacity=self.capacity // self.facility_count,
            )
            for index in range(self.facility_count)
        ]
        consumers = [
            Consumer(index, next_location(), self.demand // self.consumer_count)
            for index in range(self.consumer_count)
        ]
        domain = FacilityLocationDomain(
            facilities,
            consumers,
            self.south_west_corner,
            self.north_east_corner,
        )
        domain.validate()
        return domain
