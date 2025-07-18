# greynet/constraint_weights.py
import threading
from typing import Dict

class ConstraintWeights:
    """
    A thread-safe manager for storing and retrieving constraint weights.
    
    This object is shared between the builder and the session to allow
    for dynamic, runtime updates to constraint penalties.
    """
    def __init__(self):
        self._weights: Dict[str, float] = {}
        self._lock = threading.Lock()

    def set_weight(self, constraint_id: str, weight: float):
        """Sets the weight multiplier for a given constraint."""
        with self._lock:
            self._weights[constraint_id] = float(weight)

    def get_weight(self, constraint_id: str) -> float:
        """
        Gets the weight for a given constraint.
        
        Returns:
            The configured weight, or 1.0 as a default if not set.
        """
        with self._lock:
            return self._weights.get(constraint_id, 1.0)
