from dataclasses import dataclass
from typing import Optional


@dataclass
class Process:
    process_id: int
    cpu_power_req: int
    memory_size_req: int
    network_bandwidth_req: int
    computer_id: Optional[int] = None

    @property
    def requirements(self) -> tuple[int, int, int]:
        return self.cpu_power_req, self.memory_size_req, self.network_bandwidth_req
