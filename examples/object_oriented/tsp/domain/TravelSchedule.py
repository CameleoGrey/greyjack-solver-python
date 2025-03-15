import numpy as np
import matplotlib.pyplot as plt

class TravelSchedule():
    def __init__(self, name, vehicle, locations_list, distance_matrix):

        self.name = name
        self.vehicle = vehicle
        self.locations_list = locations_list
        self.distance_matrix = distance_matrix

        pass

    def get_unique_stops_count(self):
        unique_stops = set(self.vehicle.trip_path)
        unique_stops_count = len(unique_stops)
        return unique_stops_count
    
    def get_travel_distance(self):

        depot = self.vehicle.depot
        trip_path = self.vehicle.trip_path
        if trip_path is None or trip_path == []:
            raise Exception("Vehicle trip_path is not initialized. Probably, a TSP task isn't solved yet or domain model isn't updated.")

        depot_to_first_stop_distance = depot.get_distance_to_other_location( trip_path[0] )
        last_stop_to_depot_distance = trip_path[-1].get_distance_to_other_location( depot )

        interim_stops_distance = 0
        for i in range(1, len(trip_path)):
            stop_from = trip_path[i-1]
            stop_to = trip_path[i]
            current_distance = stop_from.get_distance_to_other_location( stop_to )
            interim_stops_distance += current_distance

        travel_distance = depot_to_first_stop_distance + interim_stops_distance + last_stop_to_depot_distance

        return travel_distance

    def print_metrics(self):
        print("Solution distance: {}".format(self.get_travel_distance()))
        print("Unique stops (excluding depot): {}".format(self.get_unique_stops_count()))

    def print_path(self):
        path_names_string = self.build_string_of_path_names()
        path_ids_string = self.build_string_of_path_ids()

        print( path_names_string )
        print( path_ids_string )
    
    def build_string_of_path_names(self):
        path_names_string = [str(self.vehicle.depot.name)]
        for stop in self.vehicle.trip_path:
            path_names_string.append( str(stop.name) )
        path_names_string.append( str(self.vehicle.depot.name) )
        path_names_string = " --> ".join( path_names_string )
        return path_names_string
    
    def build_string_of_path_ids(self):
        path_ids_string = [str(self.vehicle.depot.id)]
        for stop in self.vehicle.trip_path:
            path_ids_string.append( str(stop.id) )
        path_ids_string.append( str(self.vehicle.depot.id) )
        path_ids_string = " --> ".join( path_ids_string )
        return path_ids_string


    def plot_path(self, image_file_path=None, dpi=200):

        x_coordinates = []
        y_coordinates = []
        labels = []
        for location in self.locations_list:
            x = location.latitude
            y = location.longitude
            label = location.name

            x_coordinates.append( x )
            y_coordinates.append( y )
            labels.append( label )

        plt.scatter( x=x_coordinates, y=y_coordinates, s=1)
        for x, y, label in zip(x_coordinates, y_coordinates, labels):
            plt.text( x, y, label, fontsize=8, fontfamily="calibri" )

        edges_x = [self.vehicle.depot.latitude]
        edges_y = [self.vehicle.depot.longitude]
        trip_path = self.vehicle.trip_path
        for stop_point in trip_path:
            edges_x.append( stop_point.latitude )
            edges_y.append( stop_point.longitude )

        edges_x.append(self.vehicle.depot.latitude)
        edges_y.append(self.vehicle.depot.longitude)

        plt.plot( edges_x, edges_y, linewidth=0.5 )

        if image_file_path is None:
            plt.show()
        else:
            plt.savefig(image_file_path, dpi=dpi)
            plt.close()