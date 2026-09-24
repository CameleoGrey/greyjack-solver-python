import json
from copy import deepcopy
from pathlib import Path
from typing import Optional

from ..domain.Computer import Computer
from ..domain.Process import Process
from ..domain.ScheduleCB import ScheduleCB
from ..solver.CloudBalancingSolution import CloudBalancingSolution


class DomainBuilder:
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)

    def build_domain_from_scratch(self) -> ScheduleCB:
        with self.file_path.open(encoding="utf-8") as json_file:
            data = json.load(json_file)
        try:
            if not isinstance(data, dict):
                raise ValueError("The dataset must be a JSON object")
            if not isinstance(data["computerList"], list) or not isinstance(
                data["processList"], list
            ):
                raise ValueError("computerList and processList must be JSON arrays")
            computers = [
                Computer(
                    c["id"],
                    c["cpuPower"],
                    c["memory"],
                    c["networkBandwidth"],
                    c["cost"],
                )
                for c in data["computerList"]
            ]
            processes = [
                Process(
                    p["id"],
                    p["requiredCpuPower"],
                    p["requiredMemory"],
                    p["requiredNetworkBandwidth"],
                    p["computer"],
                )
                for p in data["processList"]
            ]
        except (KeyError, TypeError) as error:
            raise ValueError(f"Invalid cloud-balancing JSON: {error}") from error
        domain = ScheduleCB(computers, processes)
        domain.validate()
        return domain

    def build_from_domain(self, domain: ScheduleCB) -> ScheduleCB:
        return deepcopy(domain)

    def build_from_solution(
        self,
        solution: CloudBalancingSolution,
        initial_domain: Optional[ScheduleCB] = None,
    ) -> ScheduleCB:
        """Apply ID-based assignments to a copy, preserving the input domain."""
        if not solution.has_solution:
            raise ValueError(
                f"Cannot reconstruct a solution with status {solution.status}"
            )
        domain = (
            self.build_domain_from_scratch()
            if initial_domain is None
            else self.build_from_domain(initial_domain)
        )
        if set(solution.assignments) != {p.process_id for p in domain.processes}:
            raise ValueError(
                "Solution assignments must cover exactly the domain's process IDs"
            )
        for process in domain.processes:
            process.computer_id = solution.assignments[process.process_id]
        metrics = domain.calculate_metrics()
        if (metrics["hard_penalty"], metrics["soft_cost"]) != (
            solution.hard_penalty,
            solution.soft_cost,
        ):
            raise ValueError(
                "Reconstructed domain scores do not match the solver result"
            )
        return domain
