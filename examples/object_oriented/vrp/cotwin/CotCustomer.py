

class CotCustomer():
    def __init__(self, customer_vec_id, demand, time_window_start, time_window_end, service_time):

        self.customer_vec_id = customer_vec_id
        self.demand = demand
        self.time_window_start = time_window_start
        self.time_window_end = time_window_end
        self.service_time = service_time

        pass