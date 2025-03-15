

class CotCustomer():
    def __init__(self, customer_matrix_id, demand, time_window_start, time_window_end, service_time):

        self.customer_matrix_id = customer_matrix_id
        self.demand = demand
        self.time_window_start = time_window_start
        self.time_window_end = time_window_end
        self.service_time = service_time

        pass