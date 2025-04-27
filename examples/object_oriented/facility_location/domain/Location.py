import math

class Location:
    # Approximate Metric Equivalents for Degrees. At the equator for longitude and for latitude anywhere,
    # the following approximations are valid: 1° = 111 km (or 60 nautical miles) 0.1° = 11.1 km.
    METERS_PER_DEGREE = 111000

    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude

    def __str__(self):
        return f"[{self.latitude:.4f}N, {self.longitude:.4f}E]"

    def get_distance_to(self, other):
        latitude_diff = other.latitude - self.latitude
        longitude_diff = other.longitude - self.longitude
        distance_degrees = math.sqrt(latitude_diff**2 + longitude_diff**2)
        return math.ceil(distance_degrees * self.METERS_PER_DEGREE)