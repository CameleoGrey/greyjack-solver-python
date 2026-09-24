from dataclasses import dataclass

from ortools.sat.python import cp_model


@dataclass
class CotEmployeeSchedule:
    """Mathematical model and explicit mappings back to business assignments."""

    model: cp_model.CpModel
    assignment_variables: dict[int, cp_model.IntVar]
    assignment_indicators: dict[int, list[cp_model.IntVar]]
    penalty_components: dict[str, cp_model.IntVar]
    shift_counts: list[cp_model.IntVar]
    fairness_cents: cp_model.IntVar
    hard_penalty: cp_model.IntVar
    soft_penalty_cents: cp_model.IntVar
    hard_weight: int
    mode: str = "penalized"
