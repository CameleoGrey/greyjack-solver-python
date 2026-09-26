from dataclasses import dataclass, field
from datetime import timedelta


@dataclass(eq=False)
class Product:
    id: int
    name: str
    cleaning_durations: dict["Product", timedelta] = field(
        default_factory=dict, repr=False
    )

    def get_cleanup_duration(self, previous_product: "Product") -> timedelta:
        try:
            return self.cleaning_durations[previous_product]
        except KeyError as error:
            raise ValueError(
                f"Cleanup duration from {previous_product} to {self} is missing"
            ) from error

    def __str__(self) -> str:
        return self.name
