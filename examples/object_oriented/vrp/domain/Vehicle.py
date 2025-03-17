

class Vehicle():

    def __init__(self, depot, depot_vec_id, work_day_start, work_day_end, capacity, customer_list, max_stops):

        self.depot = depot
        self.depot_vec_id = depot_vec_id
        self.work_day_start = work_day_start
        self.work_day_end = work_day_end
        self.capacity = capacity
        if customer_list is None:
            customer_list = []
        self.customer_list = customer_list
        self.max_stops = max_stops

        pass