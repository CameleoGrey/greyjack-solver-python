
import math

class Location():
     def __init__(self, id, name, latitude, longitude, distances_to_other_locations_dict):

         self.id = id
         self.name = name
         self.latitude = latitude
         self.longitude = longitude
         self.distances_to_other_locations_dict = None

         pass

     def __str__(self):
         return "Location id: " + str(self.id) + " | " + self.name + ": " + "lat=" + str(self.latitude) + ", " + "lon=" + str(self.longitude)

     def get_distance_to_other_location(self, other_location):

         if self.distances_to_other_locations_dict is None:
             distance = math.sqrt((other_location.latitude - self.latitude)**2 + (other_location.longitude - self.longitude)**2)
         else:
             distance = self.distances_to_other_locations_dict[ other_location.name ]

         return distance

