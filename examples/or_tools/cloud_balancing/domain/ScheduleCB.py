from dataclasses import dataclass
from typing import Any

from .Computer import Computer
from .Process import Process


def _require_integer(value: Any, label: str, nonnegative: bool = False) -> None:
    if type(value) is not int or (nonnegative and value < 0):
        kind = "a nonnegative integer" if nonnegative else "an integer"
        raise ValueError(f"{label} must be {kind}; got {value!r}")


@dataclass
class ScheduleCB:
    computers: list[Computer]
    processes: list[Process]

    def validate(self) -> None:
        computer_ids = set()
        for computer in self.computers:
            _require_integer(computer.computer_id, "Computer ID")
            if computer.computer_id in computer_ids:
                raise ValueError(f"Duplicate computer ID: {computer.computer_id}")
            computer_ids.add(computer.computer_id)
            for field in ("cpu_power", "memory_size", "network_bandwidth", "cost"):
                _require_integer(
                    getattr(computer, field),
                    f"Computer {computer.computer_id} {field}",
                    nonnegative=True,
                )

        if self.processes and not self.computers:
            raise ValueError("Cannot assign processes without any computers")

        process_ids = set()
        for process in self.processes:
            _require_integer(process.process_id, "Process ID")
            if process.process_id in process_ids:
                raise ValueError(f"Duplicate process ID: {process.process_id}")
            process_ids.add(process.process_id)
            for field in ("cpu_power_req", "memory_size_req", "network_bandwidth_req"):
                _require_integer(
                    getattr(process, field),
                    f"Process {process.process_id} {field}",
                    nonnegative=True,
                )
            if process.computer_id is not None:
                _require_integer(process.computer_id, "Assigned computer ID")
                if process.computer_id not in computer_ids:
                    raise ValueError(
                        f"Process {process.process_id} references unknown computer "
                        f"{process.computer_id}"
                    )

    def calculate_metrics(self) -> dict[str, Any]:
        """Recompute resource usage and scores from business assignments alone."""
        self.validate()
        computers_by_id = {c.computer_id: c for c in self.computers}
        usage = {}
        for process in self.processes:
            if process.computer_id is None:
                raise ValueError(f"Process {process.process_id} is unassigned")
            current = usage.setdefault(
                process.computer_id,
                {"processes": [], "cpu": 0, "memory": 0, "network": 0},
            )
            current["processes"].append(process.process_id)
            for resource, demand in zip(
                ("cpu", "memory", "network"), process.requirements
            ):
                current[resource] += demand

        violations = 0
        hard_penalty = 0
        soft_cost = 0
        for computer_id, current in usage.items():
            computer = computers_by_id[computer_id]
            soft_cost += computer.cost
            for resource, capacity in zip(
                ("cpu", "memory", "network"), computer.resources
            ):
                overload = max(0, current[resource] - capacity)
                hard_penalty += overload
                violations += int(overload > 0)

        return {
            "computer_usage": usage,
            "total_violations": violations,
            "computers_used": len(usage),
            "hard_penalty": hard_penalty,
            "soft_cost": soft_cost,
            "resource_feasible": hard_penalty == 0,
        }

    def print_metrics(self) -> None:
        metrics = self.calculate_metrics()
        computers_by_id = {c.computer_id: c for c in self.computers}
        for computer_id, usage in sorted(metrics["computer_usage"].items()):
            computer = computers_by_id[computer_id]
            print(f"Computer {computer_id} utilization:")
            print(
                f"    CPU: {usage['cpu']} / {computer.cpu_power} | "
                f"RAM: {usage['memory']} / {computer.memory_size} | "
                f"NTWRK: {usage['network']} / {computer.network_bandwidth}"
            )
            print(f"    PIDs: {', '.join(str(pid) for pid in usage['processes'])}")
            print()
        print(f"Total violations: {metrics['total_violations']}")
        print(f"Computers used: {metrics['computers_used']}")
        print(f"Hard penalty (total overload): {metrics['hard_penalty']}")
        print(f"Soft cost (used computers): {metrics['soft_cost']}")
        print(f"Resource feasible: {metrics['resource_feasible']}")
