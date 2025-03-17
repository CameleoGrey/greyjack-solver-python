
import numpy as np
from copy import deepcopy

from examples.object_oriented.vrp.cotwin.CotCustomer import CotCustomer
from examples.object_oriented.vrp.cotwin.CotStop import CotStop
from examples.object_oriented.vrp.cotwin.CotVehicle import CotVehicle
from examples.object_oriented.vrp.cotwin.VRPCotwin import VRPCotwin
from examples.object_oriented.vrp.score.PlainScoreCalculatorVRP import PlainScoreCalculatorVRP
from examples.object_oriented.vrp.score.IncrementalScoreCalculatorVRP import IncrementalScoreCalculatorVRP

from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger

class CotwinBuilder(CotwinBuilderBase):

    def __init__(self, use_incremental_score_calculator, use_greed_init):
        self.use_incremental_score_calculator = use_incremental_score_calculator
        self.use_greed_init = use_greed_init
        pass

    def build_cotwin(self, domain, is_already_initialized):

        vrp_cotwin = VRPCotwin()

        vrp_cotwin.add_planning_entities_list(self._build_planning_stops(domain, is_already_initialized), "planning_stops")
        vrp_cotwin.add_problem_facts_list(self._build_problem_fact_vehicles(domain), "vehicles")
        vrp_cotwin.add_problem_facts_list(self._build_problem_fact_customers(domain), "customers")

        if self.use_incremental_score_calculator:
            score_calculator = IncrementalScoreCalculatorVRP()
            # to avoid joins while calculating score
            self.add_incremental_utilities(domain, score_calculator)

        else:
            score_calculator = PlainScoreCalculatorVRP()
            if not domain.time_windowed:
                score_calculator.remove_constraint("late_arrival_penalty")

        score_calculator.utility_objects["distance_matrix"] = domain.distance_matrix
        vrp_cotwin.set_score_calculator( score_calculator )

        return vrp_cotwin

    def _build_problem_fact_vehicles(self, domain):

        problem_fact_vehicles = []
        for i, domain_vehicle in enumerate(domain.vehicles):
            vehicle_id = i
            depot_vec_id = domain_vehicle.depot_vec_id
            capacity = domain_vehicle.capacity
            work_day_start = domain_vehicle.work_day_start
            work_day_end = domain_vehicle.work_day_end
            cot_vehicle = CotVehicle( vehicle_id, capacity, depot_vec_id, work_day_start, work_day_end)
            problem_fact_vehicles.append( cot_vehicle )

        return problem_fact_vehicles

    def _build_problem_fact_customers(self, domain):

        problem_fact_customers = []
        customers_dict = domain.customers_dict
        n_depots = len(domain.depot_dict)
        n_customers = len(customers_dict)

        for i in range(n_depots, n_customers):
            demand = customers_dict[i].demand
            time_window_start = customers_dict[i].time_window_start
            time_window_end = customers_dict[i].time_window_end
            service_time = customers_dict[i].service_time
            cot_customer = CotCustomer(i, demand, time_window_start, time_window_end, service_time)
            problem_fact_customers.append(cot_customer)

        return problem_fact_customers

    def _build_planning_stops(self, domain, is_already_initialized):

        planning_stops = []
        customers_dict = domain.customers_dict
        n_depots = len(domain.depot_dict)
        n_customers = len(customers_dict)
        k_vehicles = len(domain.vehicles)

        initial_vehicle_ids = [None for k in range(n_customers - n_depots)]
        initial_customer_ids = [None for i in range(n_customers - n_depots)]
        is_frozen = [False for i in range(n_customers - n_depots)]
        if is_already_initialized:
            i = 0
            for k in range(k_vehicles):
                vehicle_k = domain.vehicles[k]
                for customer in vehicle_k.customer_list:
                    initial_vehicle_ids[i] = k
                    initial_customer_ids[i] = domain.customers_id_to_vec_id_map[customer.id]
                    is_frozen[i] = customer.frozen
                    i += 1
        elif self.use_greed_init:
            initial_vehicle_ids, initial_customer_ids = self.build_greed_initial_ids(domain)

        for i in range(n_depots, n_customers):
            
            #initial_value=None
            #initial_value=i % (k_vehicles-1)
            #initial_value=initial_vehicle_ids[i - n_depots]
            #semantic_groups=["vehicle_assignment", "common"]
            planning_vehicle_id = GJInteger(0, k_vehicles-1, is_frozen[i - n_depots], initial_vehicle_ids[i - n_depots], semantic_groups=["vehicle_assignment", "common"])

            #initial_value=None
            #initial_value=i
            #initial_value=initial_customer_ids[i - n_depots]
            #semantic_groups=["customer_assignment", "common"]
            planning_customer_id = GJInteger(n_depots, n_customers-1, is_frozen[i - n_depots], initial_customer_ids[i - n_depots], semantic_groups=["customer_assignment", "common"])

            planning_stop = CotStop(planning_vehicle_id, planning_customer_id)
            planning_stops.append(planning_stop)

        return planning_stops
    

    def build_greed_initial_ids(self, domain):
        # Just iterate over vehicles and fill them by customers until vehicle will full (cumulative customers demand <= vehicle capacity).
        # Filling a vehicle by customers is made by adding nearest neighbour to previous added customer (like in TSP).
        # There are problems with time accounting, but despite this, gives much better results and much faster convergence than random init.

        n_depots = len(domain.depot_dict)
        n_locations = len(domain.customers_dict)
        distance_matrix = domain.distance_matrix

        initial_vehicle_ids = []
        initial_customer_ids = []

        customers_vec = list(domain.customers_dict.values())
        remaining_customers = set([i for i in range(len(customers_vec))][n_depots:])
        for k, vehicle in enumerate(domain.vehicles):
            if len(remaining_customers) <= 0:
                break

            vehicle_depot_id = vehicle.depot_vec_id
            vehicle_capacity = vehicle.capacity
            collected_demand = 0
            vehicle_stops = []
            # work_day_start = vehicle.work_day_start
            # work_day_end = vehicle.work_day_end
            # current_arrival_time = work_day_start

            stop_id = 0
            while collected_demand < vehicle_capacity and len(remaining_customers) > 0:
                previous_stop_id = vehicle_depot_id if len(vehicle_stops) == 0 else vehicle_stops[stop_id - 1]

                best_distance = float('inf')
                best_candidate = 999999999
                # found_acceptable_candidate = False
                for candidate_stop_id in remaining_customers:
                    # customer_i_start = domain.customers_vec[candidate_stop_id].time_window_start
                    # customer_i_end = domain.customers_vec[candidate_stop_id].time_window_end
                    # customer_i_service_time = domain.customers_vec[candidate_stop_id].service_time
                    # arrival_time_to_candidate = max(current_arrival_time, customer_i_start)
                    # if arrival_time_to_candidate > customer_i_end + customer_i_service_time:
                    #     continue
                    # if arrival_time_to_candidate + customer_i_service_time > work_day_end:
                    #     continue

                    current_distance = distance_matrix[previous_stop_id][candidate_stop_id]
                    if current_distance < best_distance:
                        # found_acceptable_candidate = True
                        best_distance = current_distance
                        best_candidate = candidate_stop_id

                        # best_candidate_start = domain.customers_vec[best_candidate].time_window_start
                        # best_candidate_service_time = domain.customers_vec[best_candidate].service_time
                        # current_arrival_time = max(current_arrival_time, best_candidate_start)
                        # current_arrival_time += best_candidate_service_time

                # if not found_acceptable_candidate:
                #     break

                best_candidate_demand = customers_vec[best_candidate].demand
                if collected_demand + best_candidate_demand <= vehicle_capacity:
                    collected_demand += best_candidate_demand
                    vehicle_stops.append(best_candidate)
                    remaining_customers.remove(best_candidate)
                else:
                    break

                stop_id += 1

            vehicle_ids = [k] * len(vehicle_stops)
            vehicle_stops = [customer_id for customer_id in vehicle_stops]

            initial_vehicle_ids.extend(vehicle_ids)
            initial_customer_ids.extend(vehicle_stops)

        # Greed init is an approximation way to fill vehicles. 
        # Probably, not all customers will fit to vehicles by this approach.
        needful_init_count = n_locations - n_depots
        if len(initial_customer_ids) < needful_init_count:
            delta_count = needful_init_count - len(initial_customer_ids)
            for _ in range(delta_count):
                initial_vehicle_ids.append(None)
                initial_customer_ids.append(None)

        return initial_vehicle_ids, initial_customer_ids
    
    def add_incremental_utilities(self, domain, score_calculator):
        k_vehicles = len(domain.vehicles)
        depot_ids = np.zeros((k_vehicles, ), dtype=np.int64)
        capacities = np.zeros((k_vehicles, ), dtype=np.int64)
        for k in range(k_vehicles):
            depot_ids[k] = domain.vehicles[k].depot_vec_id
            capacities[k] = domain.vehicles[k].capacity
        score_calculator.utility_objects["depot_ids"] = depot_ids
        score_calculator.utility_objects["vehicle_capacities"] = capacities

        n_customers = len(domain.customers_dict)
        demands = np.zeros((n_customers, ), dtype=np.int64)
        for i in range(n_customers):
            demands[i] = domain.customers_dict[i].demand
        score_calculator.utility_objects["demands"] = demands

        score_calculator.utility_objects["time_windowed"] = domain.time_windowed
        if domain.time_windowed:
            work_day_starts = np.zeros((k_vehicles, ), dtype=np.int64)
            work_day_ends = np.zeros((k_vehicles, ), dtype=np.int64)
            for k in range(k_vehicles):
                work_day_starts[k] = domain.vehicles[k].work_day_start
                work_day_ends[k] = domain.vehicles[k].work_day_end
            score_calculator.utility_objects["work_day_starts"] = work_day_starts
            score_calculator.utility_objects["work_day_ends"] = work_day_ends

            time_window_starts = np.zeros((n_customers, ), dtype=np.int64)
            time_window_ends = np.zeros((n_customers, ), dtype=np.int64)
            service_times = np.zeros((n_customers, ), dtype=np.int64)
            for i in range(n_customers):
                time_window_starts[i] = domain.customers_dict[i].time_window_start
                time_window_ends[i] = domain.customers_dict[i].time_window_end
                service_times[i] = domain.customers_dict[i].service_time
            score_calculator.utility_objects["time_window_starts"] = time_window_starts
            score_calculator.utility_objects["time_window_ends"] = time_window_ends
            score_calculator.utility_objects["service_times"] = service_times