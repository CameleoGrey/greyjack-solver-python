
import math

class Customer():
     def __init__(self, id, name, latitude, longitude, demand=None,
                  time_window_start=None, time_window_end=None, service_time=None,
                  distances_to_other_customers_dict=None):

         self.id = id
         self.name = name
         self.latitude = latitude
         self.longitude = longitude
         self.demand = demand
         self.time_window_start = time_window_start
         self.time_window_end = time_window_end
         self.service_time = service_time
         self.distances_to_other_customers_dict = distances_to_other_customers_dict

         pass

     def __str__(self):
         return ("Customer id: " + str(self.id) + " | " + self.name + ": " +
                 "latitude=" + str(self.latitude) + ", " + "longitude=" + str(self.longitude))

     def get_distance_to_other_customer(self, other_customer):

         if self.distances_to_other_customers_dict is None:
             distance = math.sqrt((other_customer.latitude - self.latitude)**2 + (other_customer.longitude - self.longitude)**2)
         else:
             distance = self.distances_to_other_customers_dict[ other_customer.name ]

         return distance

