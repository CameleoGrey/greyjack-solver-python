import math
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from ..domain import Location, TravelSchedule, Vehicle

if TYPE_CHECKING:
    from ..solver.TSPSolution import TSPSolution


class DomainBuilder:
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)

    def build_domain_from_scratch(self) -> TravelSchedule:
        headers: dict[str, str] = {}
        sections: dict[str, list[str]] = {
            "NODE_COORD_SECTION": [],
            "EDGE_WEIGHT_SECTION": [],
        }
        seen_sections: set[str] = set()
        section: str | None = None
        for raw_line in self.file_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("COMMENT"):
                continue
            if line == "EOF":
                break
            if line in sections:
                if line in seen_sections:
                    raise ValueError(f"Duplicate TSP section: {line}")
                seen_sections.add(line)
                section = line
                continue
            if section is None:
                key, separator, value = line.partition(":")
                if not separator:
                    raise ValueError(f"Invalid TSP header: {line}")
                headers[key.strip()] = value.strip()
            else:
                sections[section].append(line)

        if headers.get("TYPE", "TSP") != "TSP":
            raise ValueError("TYPE must be TSP")
        edge_type = headers.get("EDGE_WEIGHT_TYPE")
        if edge_type not in ("EUC_2D", "EXPLICIT"):
            raise ValueError("EDGE_WEIGHT_TYPE must be EUC_2D or EXPLICIT")
        if "NODE_COORD_SECTION" not in seen_sections:
            raise ValueError("TSP file requires NODE_COORD_SECTION")
        if edge_type == "EXPLICIT":
            if headers.get("EDGE_WEIGHT_FORMAT") != "FULL_MATRIX":
                raise ValueError(
                    "EXPLICIT weights require EDGE_WEIGHT_FORMAT: FULL_MATRIX"
                )
            if "EDGE_WEIGHT_SECTION" not in seen_sections:
                raise ValueError("EXPLICIT weights require EDGE_WEIGHT_SECTION")
        elif "EDGE_WEIGHT_SECTION" in seen_sections:
            raise ValueError("EUC_2D must not contain EDGE_WEIGHT_SECTION")
        try:
            name = headers["NAME"]
            dimension = int(headers["DIMENSION"])
        except (KeyError, ValueError) as error:
            raise ValueError(f"Invalid TSP header: {error}") from error
        if dimension < 2:
            raise ValueError("DIMENSION must be at least two")
        locations = []
        for line in sections["NODE_COORD_SECTION"]:
            parts = line.split(maxsplit=3)
            if len(parts) < 3:
                raise ValueError(f"Invalid coordinate row: {line}")
            try:
                location_id = int(parts[0])
                latitude = float(parts[1])
                longitude = float(parts[2])
            except ValueError as error:
                raise ValueError(f"Invalid coordinate row: {line}") from error
            locations.append(
                Location(
                    location_id,
                    parts[3] if len(parts) == 4 else str(location_id),
                    latitude,
                    longitude,
                )
            )
        if len(locations) != dimension:
            raise ValueError("DIMENSION must match NODE_COORD_SECTION length")
        if len({location.id for location in locations}) != dimension:
            raise ValueError("Location IDs must be unique integers")
        if any(
            not math.isfinite(value)
            for location in locations
            for value in (location.latitude, location.longitude)
        ):
            raise ValueError("Coordinates must be finite numbers")

        if edge_type == "EUC_2D":
            distance_scale = 1000
            distance_matrix = []
            for source in locations:
                row = []
                for target in locations:
                    scaled_distance = distance_scale * math.sqrt(
                        (source.latitude - target.latitude) ** 2
                        + (source.longitude - target.longitude) ** 2
                    )
                    if not math.isfinite(scaled_distance):
                        raise ValueError("EUC_2D distance exceeds finite range")
                    row.append(round(scaled_distance))
                distance_matrix.append(row)
        else:
            tokens = " ".join(sections["EDGE_WEIGHT_SECTION"]).split()
            if len(tokens) != dimension * dimension:
                raise ValueError(
                    "FULL_MATRIX must contain DIMENSION × DIMENSION weights"
                )
            try:
                weights = [Decimal(token) for token in tokens]
            except InvalidOperation as error:
                raise ValueError(
                    "FULL_MATRIX weights must be finite decimals"
                ) from error
            if any(not weight.is_finite() or weight < 0 for weight in weights):
                raise ValueError("FULL_MATRIX weights must be finite and nonnegative")
            places = max(
                0, *(max(0, -weight.as_tuple().exponent) for weight in weights)
            )
            distance_scale = 10**places
            values = []
            for weight in weights:
                numerator, denominator = weight.as_integer_ratio()
                scaled, remainder = divmod(numerator * distance_scale, denominator)
                if remainder:
                    raise ValueError("FULL_MATRIX weight cannot use the common scale")
                values.append(scaled)
            distance_matrix = [
                values[row * dimension : (row + 1) * dimension]
                for row in range(dimension)
            ]

        domain = TravelSchedule(
            name,
            Vehicle(locations[0].id),
            locations,
            distance_matrix,
            distance_scale,
        )
        domain.validate()
        return domain

    @staticmethod
    def build_from_domain(domain: TravelSchedule) -> TravelSchedule:
        return deepcopy(domain)

    def build_from_solution(
        self,
        solution: "TSPSolution",
        initial_domain: TravelSchedule | None = None,
    ) -> TravelSchedule:
        if not solution.has_solution:
            raise ValueError("Cannot reconstruct a result without an incumbent")
        domain = self.build_from_domain(
            self.build_domain_from_scratch()
            if initial_domain is None
            else initial_domain
        )
        domain.validate()
        if solution.tour_ids is None:
            raise ValueError("Solution has no tour")
        locations = domain.location_by_id
        expected = set(locations) - {domain.vehicle.depot_id}
        tour_ids = solution.tour_ids
        if any(
            type(location_id) is not int or location_id not in expected
            for location_id in tour_ids
        ):
            raise ValueError("Solution tour contains an unknown stop or depot")
        domain.vehicle.trip_path = [locations[location_id] for location_id in tour_ids]
        distance = domain.calculate_metrics()["distance"]
        if distance != solution.distance:
            raise ValueError(
                "Reconstructed business distance differs from solver result"
            )
        return domain
