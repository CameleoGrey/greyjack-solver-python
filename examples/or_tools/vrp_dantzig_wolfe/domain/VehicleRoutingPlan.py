import math
from dataclasses import dataclass

from .Customer import Customer
from .Vehicle import Vehicle


@dataclass
class VehicleRoutingPlan:
    name: str
    locations: list[Customer]
    depot_ids: list[int]
    vehicles: list[Vehicle]
    distance_matrix: list[list[int]]
    time_windowed: bool

    @property
    def location_by_id(self) -> dict[int, Customer]:
        return {location.id: location for location in self.locations}

    @property
    def index_by_id(self) -> dict[int, int]:
        return {location.id: index for index, location in enumerate(self.locations)}

    @property
    def customer_ids(self) -> set[int]:
        return {location.id for location in self.locations} - set(self.depot_ids)

    def validate(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Dataset name must be a nonempty string")
        ids = [location.id for location in self.locations]
        if any(type(value) is not int for value in ids) or len(ids) != len(set(ids)):
            raise ValueError("Location IDs must be unique integers")
        if (
            not self.depot_ids
            or any(type(value) is not int for value in self.depot_ids)
            or len(self.depot_ids) != len(set(self.depot_ids))
        ):
            raise ValueError("At least one distinct depot is required")
        if not set(self.depot_ids) <= set(ids):
            raise ValueError("Depot IDs must reference known locations")
        if not self.vehicles:
            raise ValueError("At least one vehicle is required")
        size = len(self.locations)
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
        for location in self.locations:
            if not isinstance(location.name, str) or not location.name:
                raise ValueError("Location names must be nonempty strings")
            if not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in (location.latitude, location.longitude)
            ):
                raise ValueError("Coordinates must be finite numbers")
            if type(location.demand) is not int or location.demand < 0:
                raise ValueError("Demands must be nonnegative integers")
            if location.id in self.depot_ids and location.demand != 0:
                raise ValueError("Depot demand must be zero")
            fields = (
                location.time_window_start,
                location.time_window_end,
                location.service_time,
            )
            if self.time_windowed:
                if any(type(value) is not int or value < 0 for value in fields):
                    raise ValueError("Time-window fields must be nonnegative integers")
                if location.time_window_start > location.time_window_end:
                    raise ValueError("Time-window start must not exceed end")
            elif any(value is not None for value in fields):
                raise ValueError("Non-windowed locations must omit time fields")
        for vehicle in self.vehicles:
            if vehicle.depot_id not in self.depot_ids:
                raise ValueError("Vehicle depot must be a known depot")
            if type(vehicle.capacity) is not int or vehicle.capacity < 0:
                raise ValueError("Vehicle capacity must be a nonnegative integer")
            if self.time_windowed:
                if (
                    type(vehicle.work_day_start) is not int
                    or type(vehicle.work_day_end) is not int
                    or vehicle.work_day_start < 0
                    or vehicle.work_day_end < vehicle.work_day_start
                ):
                    raise ValueError("Vehicle workday must have valid integer bounds")
            elif vehicle.work_day_start is not None or vehicle.work_day_end is not None:
                raise ValueError("Non-windowed vehicles must omit workday fields")

    def calculate_metrics(self) -> dict[str, int]:
        """Replay business routes without consulting decomposition scores."""
        self.validate()
        location_by_id = self.location_by_id
        index_by_id = self.index_by_id
        expected = self.customer_ids
        visited: set[int] = set()
        hard_penalty = 0
        medium_penalty = 0
        distance = 0
        used_vehicles = 0
        for vehicle in self.vehicles:
            if not vehicle.customer_list:
                continue
            used_vehicles += 1
            current_id = vehicle.depot_id
            load = 0
            clock = vehicle.work_day_start if self.time_windowed else None
            for stop in vehicle.customer_list:
                if not isinstance(stop, Customer) or stop.id not in expected:
                    raise ValueError("Route contains an unknown customer or a depot")
                if stop.id in visited:
                    raise ValueError(f"Customer {stop.id} occurs in multiple stops")
                visited.add(stop.id)
                customer = location_by_id[stop.id]
                load += customer.demand
                distance += self.distance_matrix[index_by_id[current_id]][
                    index_by_id[customer.id]
                ]
                current_id = customer.id
                if self.time_windowed:
                    clock = max(clock, customer.time_window_start)
                    clock += customer.service_time
                    medium_penalty += max(0, clock - customer.time_window_end)
            distance += self.distance_matrix[index_by_id[current_id]][
                index_by_id[vehicle.depot_id]
            ]
            hard_penalty += max(0, load - vehicle.capacity)
            if self.time_windowed:
                medium_penalty += max(0, clock - vehicle.work_day_end)
        if visited != expected:
            raise ValueError(f"Routes omit customers: {sorted(expected - visited)}")
        return {
            "hard_penalty": hard_penalty,
            "medium_penalty": medium_penalty,
            "distance": distance,
            "used_vehicles": used_vehicles,
            "served_customers": len(visited),
        }

    def print_metrics(self) -> None:
        metrics = self.calculate_metrics()
        print(f"Capacity overload: {metrics['hard_penalty']}")
        print(f"Time penalty: {metrics['medium_penalty']}")
        print(f"Solution distance: {metrics['distance']}")
        print(f"Used vehicles: {metrics['used_vehicles']}/{len(self.vehicles)}")
        print(f"Unique stops (excluding depots): {metrics['served_customers']}")

    def print_paths(self) -> None:
        locations = self.location_by_id
        indices = self.index_by_id
        for index, vehicle in enumerate(self.vehicles):
            ids = [vehicle.depot_id, *(stop.id for stop in vehicle.customer_list)]
            ids.append(vehicle.depot_id)
            length = (
                sum(
                    self.distance_matrix[indices[left]][indices[right]]
                    for left, right in zip(ids, ids[1:])
                )
                if vehicle.customer_list
                else 0
            )
            demand = sum(locations[stop.id].demand for stop in vehicle.customer_list)
            path = " --> ".join(locations[customer_id].name for customer_id in ids)
            print(
                f"Vehicle {index}: distance={length}, demand={demand}/{vehicle.capacity}"
            )
            print(path)

    def plot_paths(self) -> None:
        try:
            import matplotlib.pyplot as plt
        except ImportError as error:
            raise RuntimeError("--plot requires matplotlib") from error
        locations = self.location_by_id
        plt.scatter(
            [location.longitude for location in self.locations],
            [location.latitude for location in self.locations],
            s=12,
        )
        for vehicle in self.vehicles:
            if not vehicle.customer_list:
                continue
            route = [
                locations[vehicle.depot_id],
                *vehicle.customer_list,
                locations[vehicle.depot_id],
            ]
            plt.plot(
                [point.longitude for point in route],
                [point.latitude for point in route],
            )
        plt.title(self.name)
        plt.show()
