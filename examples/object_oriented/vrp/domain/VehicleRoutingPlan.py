import numpy as np
import matplotlib.pyplot as plt

class VehicleRoutingPlan():
    def __init__(self, name, vehicles, customers_dict, depot_dict, distance_matrix, customers_id_to_matrix_id_map, time_windowed):

        self.name = name
        self.vehicles = vehicles
        self.customers_dict = customers_dict
        self.depot_dict = depot_dict
        self.distance_matrix = distance_matrix
        self.customers_id_to_matrix_id_map = customers_id_to_matrix_id_map
        self.time_windowed = time_windowed

        pass

    def get_unique_stops_count(self):
        unique_stops = set()
        for vehicle in self.vehicles:
            for customer in vehicle.customer_list:
                unique_stops.add( customer )
        unique_stops_count = len(unique_stops)
        return unique_stops_count
    
    def get_sum_travel_distance(self):

        sum_travel_distance = 0
        for vehicle in self.vehicles:
            current_distance = self.get_trip_length( vehicle )
            sum_travel_distance += current_distance

        return sum_travel_distance

    def get_trip_length(self, vehicle):
        depot = vehicle.depot
        trip_path = vehicle.customer_list
        if trip_path is None:
            raise Exception(
                "Vehicle customer_list is not initialized. Probably, a VRP task isn't solved yet or domain model isn't updated.")
        if len(trip_path) == 0:
            return 0

        depot_to_first_stop_distance = depot.get_distance_to_other_customer(trip_path[0])
        last_stop_to_depot_distance = trip_path[-1].get_distance_to_other_customer(depot)

        interim_stops_distance = 0
        for i in range(1, len(trip_path)):
            stop_from = trip_path[i - 1]
            stop_to = trip_path[i]
            current_distance = stop_from.get_distance_to_other_customer(stop_to)
            interim_stops_distance += current_distance

        travel_distance = depot_to_first_stop_distance + interim_stops_distance + last_stop_to_depot_distance

        return travel_distance

    def get_trip_demand(self, vehicle):
        depot = vehicle.depot
        trip_path = vehicle.customer_list
        if trip_path is None:
            raise Exception(
                "Vehicle customer_list is not initialized. Probably, a VRP task isn't solved yet or domain model isn't updated.")
        if len(trip_path) == 0:
            return 0

        trip_demand = 0
        for customer in vehicle.customer_list:
            trip_demand += customer.demand

        return trip_demand

    def print_metrics(self):
        print("Solution distance: {}".format(self.get_sum_travel_distance()))
        print("Unique stops (excluding depots): {}".format(self.get_unique_stops_count()))

    def print_paths(self):

        for k, vehicle in enumerate(self.vehicles):

            path_names_string = [str(vehicle.depot.name)]
            path_ids_string = [str(vehicle.depot.id)]
            for stop in vehicle.customer_list:
                path_names_string.append( str(stop.name) )
                path_ids_string.append( str(stop.id) )
            path_names_string.append( str(vehicle.depot.name) )
            path_ids_string.append( str(vehicle.depot.id) )

            path_names_string = " --> ".join( path_names_string )

            trip_length = self.get_trip_length( vehicle )
            trip_demand = self.get_trip_demand( vehicle )

            print()
            print( "vehicle {} trip metrics: ".format(k) )
            print( "Distance: {}".format( trip_length ))
            print( "Demand / capacity: {} / {}".format( trip_demand, vehicle.capacity ) )
            print( path_names_string )
            print()

    def plot_paths(self):

        x_coordinates = []
        y_coordinates = []
        labels = []
        for customer in self.customers_dict.values():
            x = customer.latitude
            y = customer.longitude
            label = customer.name

            x_coordinates.append( x )
            y_coordinates.append( y )
            labels.append( label )

        plt.scatter( x=x_coordinates, y=y_coordinates, s=1)
        for x, y, label in zip(x_coordinates, y_coordinates, labels):
            plt.text( x, y, label, fontsize=8, fontfamily="calibri" )

        for k, vehicle in enumerate(self.vehicles):
            edges_x = [vehicle.depot.latitude]
            edges_y = [vehicle.depot.longitude]
            trip_path = vehicle.customer_list
            for stop_point in trip_path:
                edges_x.append( stop_point.latitude )
                edges_y.append( stop_point.longitude )

            edges_x.append(vehicle.depot.latitude)
            edges_y.append(vehicle.depot.longitude)

            plt.plot( edges_x, edges_y, linewidth=0.5 )

        plt.show()
