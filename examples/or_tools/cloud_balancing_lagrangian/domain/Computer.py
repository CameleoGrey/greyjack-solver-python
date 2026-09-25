from dataclasses import dataclass


@dataclass
class Computer:
    computer_id: int
    cpu_power: int
    memory_size: int
    network_bandwidth: int
    cost: int

    @property
    def resources(self) -> tuple[int, int, int]:
        return self.cpu_power, self.memory_size, self.network_bandwidth
