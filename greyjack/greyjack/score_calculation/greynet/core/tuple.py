# core/tuple.py
from enum import Enum
from dataclasses import dataclass
from typing import Any

class TupleState(Enum):
    CREATING = "CREATING"
    OK = "OK"
    UPDATING = "UPDATING"
    DYING = "DYING"
    ABORTING = "ABORTING"
    DEAD = "DEAD"

    def is_dirty(self):
        return self in {TupleState.CREATING, TupleState.UPDATING, TupleState.DYING}

@dataclass(eq=False)
class AbstractTuple:
    node: Any = None
    state: Any = None

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)
        
    def reset(self):
        """Resets the base attributes of the tuple for pooling."""
        self.node = None
        self.state = None
    
    


@dataclass(eq=False)
class UniTuple(AbstractTuple):
    fact_a: Any = None
    
    def reset(self):
        """Resets the tuple for pooling."""
        super().reset()
        self.fact_a = None


@dataclass(eq=False)
class BiTuple(AbstractTuple):
    fact_a: Any = None
    fact_b: Any = None

    def reset(self):
        """Resets the tuple for pooling."""
        super().reset()
        self.fact_a = None
        self.fact_b = None


@dataclass(eq=False)
class TriTuple(AbstractTuple):
    fact_a: Any = None
    fact_b: Any = None
    fact_c: Any = None

    def reset(self):
        """Resets the tuple for pooling."""
        super().reset()
        self.fact_a = None
        self.fact_b = None
        self.fact_c = None


@dataclass(eq=False)
class QuadTuple(AbstractTuple):
    fact_a: Any = None
    fact_b: Any = None
    fact_c: Any = None
    fact_d: Any = None

    def reset(self):
        """Resets the tuple for pooling."""
        super().reset()
        self.fact_a = None
        self.fact_b = None
        self.fact_c = None
        self.fact_d = None


@dataclass(eq=False)
class PentaTuple(AbstractTuple):
    fact_a: Any = None
    fact_b: Any = None
    fact_c: Any = None
    fact_d: Any = None
    fact_e: Any = None

    def reset(self):
        """Resets the tuple for pooling."""
        super().reset()
        self.fact_a = None
        self.fact_b = None
        self.fact_c = None
        self.fact_d = None
        self.fact_e = None
