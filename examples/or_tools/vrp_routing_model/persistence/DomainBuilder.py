import math
import re
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

from ..domain import Customer, Vehicle, VehicleRoutingPlan

if TYPE_CHECKING:
    from ..solver.VRPSolution import VRPSolution


class DomainBuilder:
    """Read VRP files and rebuild solved business routes independently."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)

    def build_domain_from_scratch(self) -> VehicleRoutingPlan:
        headers: dict[str, str] = {}
        sections: dict[str, list[str]] = {
            "NODE_COORD_SECTION": [],
            "EDGE_WEIGHT_SECTION": [],
            "DEMAND_SECTION": [],
            "DEPOT_SECTION": [],
        }
        section: str | None = None
        seen_sections: set[str] = set()
        for raw_line in self.file_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("COMMENT"):
                continue
            if line == "EOF":
                break
            if line in sections:
                if line in seen_sections:
                    raise ValueError(f"Duplicate VRP section: {line}")
                seen_sections.add(line)
                section = line
                continue
            if section is None:
                key, separator, value = line.partition(":")
                if not separator:
                    raise ValueError(f"Invalid VRP header: {line}")
                headers[key.strip()] = value.strip()
            elif section == "DEPOT_SECTION":
                for token in line.split():
                    if token == "-1":
                        section = None
                        break
                    sections["DEPOT_SECTION"].append(token)
            else:
                sections[section].append(line)
        edge_type = headers.get("EDGE_WEIGHT_TYPE")
        if edge_type not in ("EUC_2D", "EXPLICIT"):
            raise ValueError("EDGE_WEIGHT_TYPE must be EUC_2D or EXPLICIT")
        if edge_type == "EXPLICIT":
            if headers.get("EDGE_WEIGHT_FORMAT") != "FULL_MATRIX":
                raise ValueError("EXPLICIT distances require EDGE_WEIGHT_FORMAT: FULL_MATRIX")
            if "EDGE_WEIGHT_SECTION" not in seen_sections:
                raise ValueError("EXPLICIT distances require EDGE_WEIGHT_SECTION")
        elif "EDGE_WEIGHT_SECTION" in seen_sections:
            raise ValueError("EUC_2D distances must not contain EDGE_WEIGHT_SECTION")
        if not {"NODE_COORD_SECTION", "DEMAND_SECTION", "DEPOT_SECTION"} <= seen_sections:
            raise ValueError("VRP file requires coordinate, demand, and depot sections")
        try:
            name = headers["NAME"]
            dimension = int(headers["DIMENSION"])
            capacity = int(headers["CAPACITY"])
            vehicle_match = re.search(r"-k(\d+)$", name)
            if vehicle_match is None:
                raise ValueError("VRP NAME must end with -k<vehicle count>")
            vehicle_count = int(vehicle_match.group(1))
            coordinates: dict[int, tuple[str, float, float]] = {}
            for line in sections["NODE_COORD_SECTION"]:
                parts = line.split(maxsplit=3)
                if len(parts) < 3:
                    raise ValueError(f"Invalid coordinate row: {line}")
                location_id = int(parts[0])
                if location_id in coordinates:
                    raise ValueError(f"Duplicate location ID: {location_id}")
                coordinates[location_id] = (
                    parts[3] if len(parts) == 4 else str(location_id),
                    float(parts[1]),
                    float(parts[2]),
                )
            demands: dict[int, tuple[int, int | None, int | None, int | None]] = {}
            row_widths: set[int] = set()
            for line in sections["DEMAND_SECTION"]:
                parts = line.split()
                row_widths.add(len(parts))
                if len(parts) not in (2, 5):
                    raise ValueError(f"Invalid demand row: {line}")
                location_id = int(parts[0])
                if location_id in demands:
                    raise ValueError(f"Duplicate demand ID: {location_id}")
                values = tuple(int(value) for value in parts[1:])
                demands[location_id] = (
                    values[0],
                    *(values[1:] if len(values) == 4 else (None, None, None)),
                )
            depot_ids = [int(line) for line in sections["DEPOT_SECTION"]]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid VRP file: {error}") from error
        if dimension < 1 or capacity < 0 or vehicle_count < 1:
            raise ValueError("DIMENSION and vehicle count must be positive; CAPACITY must be nonnegative")
        if dimension != len(coordinates) or set(coordinates) != set(demands):
            raise ValueError("DIMENSION, coordinates, and demand IDs must match")
        if row_widths not in ({2}, {5}):
            raise ValueError("All demand rows must use the same time-window format")
        if not depot_ids:
            raise ValueError("VRP file must contain at least one depot")
        time_windowed = row_widths == {5}
        locations = [
            Customer(location_id, *coordinates[location_id], *demands[location_id])
            for location_id in coordinates
        ]
        vehicles = []
        for vehicle_index in range(vehicle_count):
            depot_id = depot_ids[vehicle_index % len(depot_ids)]
            depot = next(
                (location for location in locations if location.id == depot_id), None
            )
            vehicles.append(
                Vehicle(
                    depot_id=depot_id,
                    capacity=capacity,
                    work_day_start=depot.time_window_start
                    if time_windowed and depot
                    else None,
                    work_day_end=depot.time_window_end
                    if time_windowed and depot
                    else None,
                )
            )
        if edge_type == "EXPLICIT":
            tokens = " ".join(sections["EDGE_WEIGHT_SECTION"]).split()
            if len(tokens) != dimension * dimension:
                raise ValueError("FULL_MATRIX must contain DIMENSION × DIMENSION distances")
            try:
                values = [int(token) for token in tokens]
            except ValueError as error:
                raise ValueError("FULL_MATRIX distances must be integers") from error
            distance_matrix = [
                values[row * dimension : (row + 1) * dimension]
                for row in range(dimension)
            ]
        else:
            distance_matrix = [
                [
                    int(
                        round(
                            1000
                            * math.sqrt(
                                (source.latitude - target.latitude) ** 2
                                + (source.longitude - target.longitude) ** 2
                            )
                        )
                    )
                    for target in locations
                ]
                for source in locations
            ]
        domain = VehicleRoutingPlan(
            name, locations, depot_ids, vehicles, distance_matrix, time_windowed
        )
        domain.validate()
        return domain

    @staticmethod
    def build_from_domain(domain: VehicleRoutingPlan) -> VehicleRoutingPlan:
        return deepcopy(domain)

    def build_from_solution(
        self,
        solution: "VRPSolution",
        initial_domain: VehicleRoutingPlan | None = None,
    ) -> VehicleRoutingPlan:
        if not solution.has_solution:
            raise ValueError("Cannot reconstruct a result without an incumbent")
        domain = self.build_from_domain(
            self.build_domain_from_scratch()
            if initial_domain is None
            else initial_domain
        )
        domain.validate()
        if solution.routes is None or len(solution.routes) != len(domain.vehicles):
            raise ValueError("Solution route count differs from vehicle count")
        locations = domain.location_by_id
        for vehicle, route in zip(domain.vehicles, solution.routes):
            if any(
                type(customer_id) is not int or customer_id not in domain.customer_ids
                for customer_id in route
            ):
                raise ValueError("Solution route contains an unknown customer ID")
            vehicle.customer_list = [locations[customer_id] for customer_id in route]
        metrics = domain.calculate_metrics()
        if (
            metrics["hard_penalty"],
            metrics["medium_penalty"],
            metrics["distance"],
        ) != (solution.hard_penalty, solution.medium_penalty, solution.distance):
            raise ValueError(
                "Reconstructed business scores differ from the solver result"
            )
        return domain
