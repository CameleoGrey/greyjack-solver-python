

import re
import numpy as np
from numba import jit
from examples.object_oriented.tsp.domain.TravelSchedule import TravelSchedule
from examples.object_oriented.tsp.domain.Vehicle import Vehicle
from examples.object_oriented.tsp.domain.Location import Location
from greyjack.persistence.DomainBuilderBase import DomainBuilderBase

class DomainBuilder(DomainBuilderBase):

    def __init__(self, file_path):

        super().__init__()

        self.file_path = file_path

        pass

    def build_domain_from_scratch(self):

        read_file = self._read_tsp_file( self.file_path )

        dataset_name = read_file["metadata"]["dataset_name"]
        locations_list = read_file["locations_list"]
        distance_matrix = None
        if "distance_matrix" in read_file:
            distance_matrix = read_file["distance_matrix"]
            for i in range(len(locations_list)):
                distances_to_other_locations_dict = {}
                for j in range(len(locations_list)):
                    current_distance = distance_matrix[i][j]
                    to_location_name = locations_list[j].name
                    distances_to_other_locations_dict[to_location_name] = current_distance
                locations_list[i].distances_to_other_locations_dict = distances_to_other_locations_dict
        else:
            distance_matrix = self._build_distance_matrix( locations_list )

        depot = locations_list[0]
        vehicle = Vehicle(depot, trip_path=None)

        domain_model = TravelSchedule(name=dataset_name,
                                      vehicle=vehicle,
                                      locations_list=locations_list,
                                      distance_matrix=distance_matrix)

        return domain_model

    def build_from_solution(self, solution, initial_domain=None):
        
        domain  = self.build_domain_from_scratch()
        path_stop_ids = []
        for planning_stop_name in solution.variable_values_dict:
            location_id = solution.variable_values_dict[planning_stop_name]
            path_stop_ids.append( location_id )

        trip_path = []
        for location_id in path_stop_ids:
            current_location = domain.locations_list[location_id]
            trip_path.append( current_location )
        domain.vehicle.trip_path = trip_path

        return domain
    
    def build_from_domain(self, domain):
        return super().build_from_domain(domain)
        
    def _build_distance_matrix(self, locations_list):

        @staticmethod
        @jit(nopython=True, cache=True)
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

    def _read_tsp_file(self, file_path):

        def read_metadata( file_pointer ):
            metadata = {}
            readed_line = ""
            while True:
                readed_line = tsp_file.readline()
                if "NODE_COORD_SECTION" in readed_line:
                    break

                if "NAME" in readed_line:
                    dataset_name = readed_line.split(" ")[-1]
                    dataset_name = dataset_name.replace("\n", "")
                    metadata["dataset_name"] = dataset_name

                if "EDGE_WEIGHT_TYPE" in readed_line:
                    distance_type = readed_line.split(" ")[-1]
                    distance_type = distance_type.replace("\n", "")
                    metadata["distance_type"] = distance_type

                pass

            return metadata

        def read_locations_list( file_pointer ):
            locations_list = []
            readed_line = ""
            while True:
                readed_line = file_pointer.readline()
                if "EOF" in readed_line or "EDGE_WEIGHT_SECTION" in readed_line:
                    break

                readed_line = readed_line.strip()
                readed_line = re.sub(" +", " ", readed_line)
                readed_line = readed_line.split(" ")
                id = int( readed_line[0] )
                latitude = float( readed_line[1] )
                longitude = float( readed_line[2] )
                if len(readed_line) > 3:
                    name = readed_line[3].replace("\n", "")
                else:
                    name = str(id)
                current_location = Location( id=id, latitude=latitude, longitude=longitude, name=name, distances_to_other_locations_dict=None )
                locations_list.append( current_location )

            return locations_list

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

        read_file_dict = {}
        with open( file_path, "r" ) as tsp_file:
            metadata = read_metadata( tsp_file )
            locations_list = read_locations_list( tsp_file )

            if metadata["distance_type"] != "EUC_2D":
                distance_matrix = read_distance_matrix( tsp_file )
                read_file_dict["distance_matrix"] = distance_matrix

            read_file_dict["metadata"] = metadata
            read_file_dict["locations_list"] = locations_list

        return read_file_dict
