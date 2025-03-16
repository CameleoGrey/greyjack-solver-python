
import re
import numpy as np
from numba import jit

from examples.object_oriented.vrp.domain.VehicleRoutingPlan import VehicleRoutingPlan
from examples.object_oriented.vrp.domain.Vehicle import Vehicle
from examples.object_oriented.vrp.domain.Customer import Customer
from greyjack.persistence.DomainBuilderBase import DomainBuilderBase

class DomainBuilder(DomainBuilderBase):

    def __init__(self, file_path):

        self.file_path = file_path

        pass

    def build_domain_from_scratch(self):

        read_file = self._read_vrp_file( self.file_path )

        dataset_name = read_file["metadata"]["dataset_name"]
        time_windowed = read_file["metadata"]["time_window_task_type"]
        customers_dict = read_file["customers_dict"]
        customers_id_to_matrix_id_map = {}
        for i in range(len(customers_dict)):
            customers_id_to_matrix_id_map[i] = customers_dict[i].id

        if "distance_matrix" in read_file:
            distance_matrix = read_file["distance_matrix"]
            for i in range(len(customers_dict)):
                distances_to_other_customers_dict = {}
                for j in range(len(customers_dict)):
                    current_distance = distance_matrix[i][j]
                    to_customer_name = customers_dict[j].name
                    distances_to_other_customers_dict[to_customer_name] = current_distance
                customers_dict[i].distances_to_other_customers_dict = distances_to_other_customers_dict
        else:
            customers_list = [customers_dict[i] for i in range(len(customers_dict))]
            distance_matrix = self._build_distance_matrix( customers_list )


        vehicles_capacity = read_file["metadata"]["vehicles_capacity"]
        k_vehicles = read_file["metadata"]["vehicles_count"]
        depot_dict = read_file["depot_dict"]
        n_depots = len(depot_dict)
        max_stops = len(customers_dict) - n_depots

        vehicles_list = []
        for i in range(k_vehicles):
            depot_matrix_id = i % n_depots
            depot = customers_dict[depot_matrix_id]
            work_day_start = depot.time_window_start
            work_day_end = depot.time_window_end
            vehicle = Vehicle(depot, depot_matrix_id, work_day_start, work_day_end,
                              vehicles_capacity, None, max_stops)
            vehicles_list.append( vehicle )

        domain_model = VehicleRoutingPlan(name=dataset_name,
                                          vehicles=vehicles_list,
                                          customers_dict=customers_dict,
                                          depot_dict=depot_dict,
                                          distance_matrix=distance_matrix,
                                          customers_id_to_matrix_id_map=customers_id_to_matrix_id_map,
                                          time_windowed=time_windowed)

        return domain_model

    def build_from_solution(self, solution):

        domain = self.build_domain_from_scratch()

        solution_dict = solution.variable_values_dict
        solution_keys = list(solution_dict.keys())

        for i in range(0, len(solution_dict), 2):
            vehicle_id = solution_dict[solution_keys[i]]
            customer_id = solution_dict[solution_keys[i+1]]
            customer = domain.customers_dict[customer_id]

            if domain.vehicles[vehicle_id].customer_list is None:
                domain.vehicles[vehicle_id].customer_list = []

            domain.vehicles[vehicle_id].customer_list.append( customer )

        return domain

    def build_from_domain(self, domain):
        return super().build_from_domain(domain)

    def _build_distance_matrix(self, locations_list):

        @staticmethod
        @jit()
        def compute_distance_matrix(latitudes, longitudes, n_locations):
            distance_matrix = np.zeros( (n_locations, n_locations), dtype=np.int64 )
            for i in range(n_locations):
                for j in range(n_locations):
                    distance_from_to = np.sqrt((latitudes[i] - latitudes[j])**2 + (longitudes[i] - longitudes[j])**2)
                    distance_matrix[i][j] = round(1000 * distance_from_to, 0)
            return distance_matrix

        n_locations = len(locations_list)
        latitudes = np.zeros((n_locations, ), dtype=np.float64)
        longitudes = np.zeros((n_locations, ), dtype=np.float64)
        for i, location in enumerate(locations_list):
            latitudes[i] = location.latitude
            longitudes[i] = location.longitude
    
        distance_matrix = compute_distance_matrix(latitudes, longitudes, n_locations)

        return distance_matrix

    def _read_vrp_file(self, file_path, for_json=False):

        def read_metadata( file_pointer ):
            metadata = {}
            readed_line = ""

            while True:
                readed_line = file_pointer.readline()
                if "NODE_COORD_SECTION" in readed_line:
                    break

                readed_line = readed_line.replace("\n", "").strip()

                if "NAME" in readed_line:
                    task_name = readed_line.split(" ")[-1]
                    vehicle_count = task_name.split("-")[-1]
                    vehicle_count = int(vehicle_count.replace("k", ""))
                    metadata["vehicles_count"] = vehicle_count

                if "TYPE" in readed_line:
                    task_type = readed_line.split(" ")[-1]
                    task_type = task_type
                    metadata["task_type"] = task_type

                if "NAME" in readed_line:
                    dataset_name = readed_line.split(" ")[-1]
                    metadata["dataset_name"] = dataset_name

                if "EDGE_WEIGHT_TYPE" in readed_line:
                    distance_type = readed_line.split(" ")[-1]
                    distance_type = distance_type
                    metadata["distance_type"] = distance_type

                if "CAPACITY" in readed_line:
                    vehicles_capacity = readed_line.split(" ")[-1]
                    metadata["vehicles_capacity"] = int(vehicles_capacity)

                pass

            return metadata

        def read_customers_common_info( file_pointer, for_json=False ):
            customers_dict = {}
            customer_matrix_id = 0
            readed_line = ""

            while True:
                readed_line = file_pointer.readline()
                if "EOF" in readed_line or "DEMAND_SECTION" in readed_line:
                    break

                readed_line = readed_line.strip()
                readed_line = re.sub(" +", " ", readed_line)
                readed_line = readed_line.split(" ")

                if for_json:
                    id = int( readed_line[0] )
                    latitude = float( readed_line[1] )
                    longitude = float( readed_line[2] )
                    if len(readed_line) > 3:
                        name = readed_line[3].replace("\n", "")
                    else:
                        name = str(id)
                    customers_dict[str(customer_matrix_id)] = {
                        "id": id,
                        "latitude": latitude,
                        "longitude": longitude,
                        "name": name
                    }
                else:
                    id = int( readed_line[0] )
                    latitude = float( readed_line[1] )
                    longitude = float( readed_line[2] )
                    if len(readed_line) > 3:
                        name = readed_line[3].replace("\n", "")
                    else:
                        name = str(id)
                    current_customer = Customer(id=id, latitude=latitude, longitude=longitude, name=name)
                    customers_dict[customer_matrix_id] = current_customer

                customer_matrix_id += 1

            return customers_dict

        def read_distance_matrix( file_pointer ):
            distance_matrix = []
            readed_line = ""

            while True:
                readed_line = file_pointer.readline()
                if "EOF" in readed_line:
                    break

                readed_line = readed_line.split(" ")
                readed_line.pop(-1)
                matrix_row = [float(value) for value in readed_line]
                matrix_row = np.array( matrix_row, dtype=np.float32 )
                distance_matrix.append( matrix_row )

            distance_matrix = np.array( distance_matrix, dtype=np.float32 )

            return distance_matrix

        def read_customers_demand( file_pointer, customers_dict, for_json=False ):
            customer_matrix_id = 0
            readed_line = ""
            time_window_task_type = False

            while True:
                readed_line = file_pointer.readline()
                if "EOF" in readed_line or "DEPOT_SECTION" in readed_line:
                    break

                readed_line = readed_line.strip()
                readed_line = re.sub(" +", " ", readed_line)
                readed_line = readed_line.split(" ")

                if for_json:
                    customers_dict[str(customer_matrix_id)]["demand"] = float(readed_line[1])
                    if len(readed_line) == 5:
                        time_window_task_type = True
                        customers_dict[str(customer_matrix_id)]["time_window_start"] = int(readed_line[2])
                        customers_dict[str(customer_matrix_id)]["time_window_end"] = int(readed_line[3])
                        customers_dict[str(customer_matrix_id)]["service_time"] = int(readed_line[4].replace("\n", ""))
                else:
                    customers_dict[customer_matrix_id].demand = float(readed_line[1])
                    if len(readed_line) == 5:
                        time_window_task_type = True
                        customers_dict[customer_matrix_id].time_window_start = int(readed_line[2])
                        customers_dict[customer_matrix_id].time_window_end = int(readed_line[3])
                        customers_dict[customer_matrix_id].service_time = int(readed_line[4].replace("\n", ""))

                customer_matrix_id += 1

            return customers_dict, time_window_task_type

        def read_depot_dict( file_pointer, for_json=False ):
            depot_dict = {}
            matrix_id = 0
            readed_line = ""

            while True:
                readed_line = file_pointer.readline()
                if "EOF" in readed_line or "-1" in readed_line:
                    break

                readed_line = readed_line.strip().replace("\n", "")
                depot_id = int(readed_line)
                if for_json:
                    depot_dict[str(matrix_id)] = depot_id
                else:
                    depot_dict[matrix_id] = depot_id
                matrix_id += 1

            return depot_dict

        read_file_dict = {}
        with open( file_path, "r" ) as vrp_file:
            metadata = read_metadata( vrp_file )
            customers_dict = read_customers_common_info( vrp_file, for_json )

            if metadata["distance_type"] != "EUC_2D":
                distance_matrix = read_distance_matrix( vrp_file )
                read_file_dict["distance_matrix"] = distance_matrix

            customers_dict, time_window_task_type = read_customers_demand( vrp_file, customers_dict, for_json )
            metadata["time_window_task_type"] = time_window_task_type
            depot_dict = read_depot_dict( vrp_file, for_json )

            read_file_dict["metadata"] = metadata
            read_file_dict["customers_dict"] = customers_dict
            read_file_dict["depot_dict"] = depot_dict

        return read_file_dict

    """def build_domain_from_json(self, domain_json):

        dataset_name = domain_json["name"]
        time_windowed = domain_json["time_windowed"]
        distance_matrix = domain_json["distance_matrix"]

        customers_json_values = domain_json["customers_vec"]
        depot_json_values = domain_json["depot_vec"]
        vehicles_json_values = domain_json["vehicles"]

        customers_vec = []
        for i, customer_json in enumerate(customers_json_values):
            customer_i = Customer(
                id = customer_json["id"],
                name = customer_json["name"],
                latitude = customer_json["latitude"],
                longitude = customer_json["longitude"],
                demand = customer_json["demand"],
                time_window_start = customer_json["time_window_start"],
                time_window_end = customer_json["time_window_end"],
                service_time = customer_json["service_time"],
                distances_to_other_customers_dict = None,
            )
            customers_vec.append( customer_i )
        
        depot_vec = []
        for i, depot_json in enumerate(depot_json_values):
            depot_i = Customer(
                id = depot_json["id"],
                name = depot_json["name"],
                latitude = depot_json["latitude"],
                longitude = depot_json["longitude"],
                demand = depot_json["demand"],
                time_window_start = depot_json["time_window_start"],
                time_window_end = depot_json["time_window_end"],
                service_time = depot_json["service_time"],
                distances_to_other_customers_dict = None,
            )
            depot_vec.append( depot_i )
        
        vehicles_vec = []
        for k, vehicle_json in enumerate(vehicles_json_values):
            vehicle_k = Vehicle(
                depot = customers_vec[vehicle_json["depot"]["vec_id"]],
                depot_matrix_id = vehicle_json["depot"]["vec_id"],
                work_day_start = vehicle_json["work_day_start"],
                work_day_end = vehicle_json["work_day_end"],
                capacity = vehicle_json["capacity"],
                customer_list = [customers_vec[customer_json["vec_id"]] for customer_json in vehicle_json["customers"]],
                max_stops = vehicle_json["max_stops"],
            )
            vehicles_vec.append(vehicle_k)

        domain_model = VehicleRoutingPlan(name=dataset_name,
                                          vehicles=vehicles_vec,
                                          customers_dict=customers_vec,
                                          depot_dict=depot_vec,
                                          distance_matrix=distance_matrix,
                                          customers_id_to_matrix_id_map=None,
                                          time_windowed=time_windowed)

        return domain_model"""