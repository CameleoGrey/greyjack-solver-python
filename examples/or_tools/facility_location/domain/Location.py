from dataclasses import dataclass
from math import ceil, isfinite, sqrt


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float

    METERS_PER_DEGREE = 111_000

    def validate(self) -> None:
        if (
            isinstance(self.latitude, bool)
            or not isinstance(self.latitude, (int, float))
            or not isfinite(self.latitude)
            or not -90 <= self.latitude <= 90
        ):
            raise ValueError(f"Invalid latitude: {self.latitude!r}")
        if (
            isinstance(self.longitude, bool)
            or not isinstance(self.longitude, (int, float))
            or not isfinite(self.longitude)
            or not -180 <= self.longitude <= 180
        ):
            raise ValueError(f"Invalid longitude: {self.longitude!r}")

    def get_distance_to(self, other: "Location") -> int:
        latitude_diff = other.latitude - self.latitude
        longitude_diff = other.longitude - self.longitude
        return ceil(sqrt(latitude_diff**2 + longitude_diff**2) * self.METERS_PER_DEGREE)

    def __str__(self) -> str:
        return f"[{self.latitude:.4f}N, {self.longitude:.4f}E]"
