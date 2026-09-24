import math
from dataclasses import dataclass
from decimal import Decimal, localcontext

from .Location import Location
from .Vehicle import Vehicle


@dataclass
class TravelSchedule:
    name: str
    vehicle: Vehicle
    locations_list: list[Location]
    distance_matrix: list[list[int]]
    distance_scale: int

    @property
    def location_by_id(self) -> dict[int, Location]:
        return {location.id: location for location in self.locations_list}

    @property
    def index_by_id(self) -> dict[int, int]:
        return {
            location.id: index for index, location in enumerate(self.locations_list)
        }

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Dataset name must be a nonempty string")
        if len(self.locations_list) < 2:
            raise ValueError("TSP requires a depot and at least one other location")
        ids = [location.id for location in self.locations_list]
        if any(type(value) is not int for value in ids) or len(ids) != len(set(ids)):
            raise ValueError("Location IDs must be unique integers")
        if self.vehicle.depot_id != ids[0]:
            raise ValueError("The depot must be the first listed location")
        for location in self.locations_list:
            if not isinstance(location.name, str) or not location.name:
                raise ValueError("Location names must be nonempty strings")
            if not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in (location.latitude, location.longitude)
            ):
                raise ValueError("Coordinates must be finite numbers")
        size = len(ids)
        if len(self.distance_matrix) != size or any(
            len(row) != size for row in self.distance_matrix
        ):
            raise ValueError("Distance matrix must be square and match locations")
        if any(
            type(distance) is not int or distance < 0
            for row in self.distance_matrix
            for distance in row
        ):
            raise ValueError("Distances must be nonnegative integers")
        if type(self.distance_scale) is not int or self.distance_scale < 1:
            raise ValueError("Distance scale must be a positive integer")

    def calculate_metrics(self) -> dict[str, int]:
        """Replay the business route without reading solver variables."""
        self.validate()
        if self.vehicle.trip_path is None:
            raise ValueError("Vehicle trip_path is not initialized")
        expected = set(self.location_by_id) - {self.vehicle.depot_id}
        route_ids = []
        for stop in self.vehicle.trip_path:
            if not isinstance(stop, Location) or stop.id not in expected:
                raise ValueError("Route contains an unknown location or the depot")
            route_ids.append(stop.id)
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("Route repeats a location")
        if set(route_ids) != expected:
            raise ValueError(
                f"Route omits locations: {sorted(expected - set(route_ids))}"
            )
        indices = self.index_by_id
        tour = [self.vehicle.depot_id, *route_ids, self.vehicle.depot_id]
        distance = sum(
            self.distance_matrix[indices[left]][indices[right]]
            for left, right in zip(tour, tour[1:])
        )
        return {"distance": distance, "unique_stops": len(route_ids)}

    def get_travel_distance(self) -> int:
        return self.calculate_metrics()["distance"]

    def print_metrics(self) -> None:
        metrics = self.calculate_metrics()
        with localcontext() as context:
            context.prec = max(
                28,
                len(str(metrics["distance"])) + len(str(self.distance_scale)) + 2,
            )
            input_distance = Decimal(metrics["distance"]) / Decimal(self.distance_scale)
        print(f"Solution distance (matrix units): {metrics['distance']}")
        print(f"Solution distance (input units): {input_distance:f}")
        print(f"Unique stops (excluding depot): {metrics['unique_stops']}")

    def print_path(self) -> None:
        self.calculate_metrics()
        assert self.vehicle.trip_path is not None
        depot = self.location_by_id[self.vehicle.depot_id]
        tour = [depot, *self.vehicle.trip_path, depot]
        print(" --> ".join(location.name for location in tour))
        print(" --> ".join(str(location.id) for location in tour))

    def plot_path(self, image_file_path: str | None = None, dpi: int = 200) -> None:
        self.calculate_metrics()
        assert self.vehicle.trip_path is not None
        try:
            import matplotlib.pyplot as plt
        except ImportError as error:
            raise RuntimeError("Plotting requires matplotlib") from error
        depot = self.location_by_id[self.vehicle.depot_id]
        tour = [depot, *self.vehicle.trip_path, depot]
        plt.scatter(
            [location.latitude for location in self.locations_list],
            [location.longitude for location in self.locations_list],
            s=12,
        )
        plt.plot(
            [location.latitude for location in tour],
            [location.longitude for location in tour],
        )
        plt.title(self.name)
        if image_file_path is None:
            plt.show()
        else:
            plt.savefig(image_file_path, dpi=dpi)
            plt.close()
