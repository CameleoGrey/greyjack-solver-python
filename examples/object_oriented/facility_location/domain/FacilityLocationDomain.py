

from examples.object_oriented.facility_location.domain import Location

class FacilityLocationDomain:
    def __init__(self, facilities=None, consumers=None, south_west_corner=None, north_east_corner=None):
        self.facilities = facilities if facilities is not None else []
        self.consumers = consumers if consumers is not None else []
        self.score = None
        self.south_west_corner = south_west_corner
        self.north_east_corner = north_east_corner
        # Constraint weight overrides placeholder
        self.constraint_weight_overrides = {"distance from facility": (0, 6)}  # (hard, soft) weights

    def print_metrics(self):
        if self.consumers is None or len(self.consumers) == 0:
            print("No cosumers. Check domain initialization.")
        
        total_distance = 0
        facilities_usages = {}
        for consumer in self.consumers:
            total_distance += consumer.distance_from_facility()

            if consumer.facility not in facilities_usages:
                facilities_usages[consumer.facility] = 0

            facilities_usages[consumer.facility] += consumer.demand
        
        total_setup_cost = 0
        for facility in facilities_usages.keys():
            total_setup_cost += facility.setup_cost
        
        print("Facility usages:")
        for facility in facilities_usages:
            facility_id = facility.id
            facility_usage = facilities_usages[facility]
            facility_capacity = facility.capacity
            print("{}: {}/{}".format(facility_id, facility_usage, facility_capacity))
        print("Total distance: {} m".format(total_distance))
        print("Total setup cost: {}$".format(total_setup_cost))



    @classmethod
    def empty(cls):
        return cls(
            facilities=[],
            consumers=[],
            south_west_corner=Location(-90, -180),
            north_east_corner=Location(90, 180)
        )

    def get_bounds(self):
        return [self.south_west_corner, self.north_east_corner]

    def get_total_cost(self):
        return sum(facility.setup_cost for facility in self.facilities if facility.is_used())

    def get_potential_cost(self):
        return sum(facility.setup_cost for facility in self.facilities)

    def get_total_distance(self):
        distance = sum(consumer.distance_from_facility() 
                      for consumer in self.consumers if consumer.is_assigned())
        return f"{distance // 1000} km"

    def __str__(self):
        return (f"FacilityLocationProblem{{facilities: {len(self.facilities)}, "
                f"consumers: {len(self.consumers)}, score: {self.score}}}")