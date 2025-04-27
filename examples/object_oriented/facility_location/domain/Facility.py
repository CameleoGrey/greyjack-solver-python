class Facility:
    """
    Facility satisfies consumers' demand. Cumulative demand of all consumers assigned to this facility must not exceed
    the facility's capacity. This requirement is expressed by the facility capacity constraint.
    """
    
    def __init__(self, id=None, location=None, setup_cost=None, capacity=None):
        self.id = id
        self.location = location
        self.setup_cost = setup_cost
        self.capacity = capacity

    def get_used_capacity(self):
        return sum(consumer.demand for consumer in self.consumers)

    def is_used(self):
        return len(self.consumers) > 0

    def __str__(self):
        return f"Facility {self.id} (${self.setup_cost}, {self.capacity} cap)"