# greynet/constraint.py
from __future__ import annotations
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .streams.abstract_stream import AbstractStream

class Constraint:
    """
    A data-only class that holds the definition of a constraint before it is
    fully processed by the ConstraintBuilder.
    
    By moving this class to its own file, we break the circular dependency between
    the 'builder' and 'streams' modules.
    """
    def __init__(self, stream: 'AbstractStream', score_type: str, penalty_function: Callable, constraint_id: str = None):
        self.stream = stream
        self.constraint_id = constraint_id
        self.score_type = score_type
        self.penalty_function = penalty_function
