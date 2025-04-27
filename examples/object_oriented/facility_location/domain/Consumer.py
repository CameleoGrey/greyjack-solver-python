class Consumer:
    """
    Consumer has a demand that can be satisfied by any Facility with sufficient capacity.
    
    Closer facilities are preferred as the distance affects travel time, signal quality, etc.
    This requirement is expressed by the distance from facility constraint.
    
    One of the FLP's goals is to minimize total set-up cost by selecting cheaper facilities.
    This requirement is expressed by the setup cost constraint.
    """

    def __init__(self, id=None, location=None, demand=None):
        self.id = id
        self.location = location
        self.demand = demand
        self.facility = None

    def is_assigned(self):
        return self.facility is not None

    def distance_from_facility(self):
        """
        Get distance from the facility.
        
        Returns:
            distance in meters
        
        Raises:
            RuntimeError: if no facility is assigned
        """
        if self.facility is None:
            raise RuntimeError("No facility is assigned.")
        return self.facility.location.get_distance_to(self.location)

    def __str__(self):
        return f"Consumer {self.id} ({self.demand} dem)"