# greynet/tuple_tools.py
from __future__ import annotations
from typing import Type, List, TypeVar
from functools import lru_cache

from .core.tuple import (
    AbstractTuple, UniTuple, BiTuple, TriTuple, QuadTuple, PentaTuple
)

# A TypeVar for generic type hints, bound to our base tuple class
T_Tuple = TypeVar('T_Tuple', bound=AbstractTuple)

# --- Mappings for quick lookups ---
ARITY_TO_TUPLE: dict[int, Type[AbstractTuple]] = {
    1: UniTuple,
    2: BiTuple,
    3: TriTuple,
    4: QuadTuple,
    5: PentaTuple,
}

TUPLE_TO_ARITY: dict[Type[AbstractTuple], int] = {v: k for k, v in ARITY_TO_TUPLE.items()}

# --- Core Utility Functions ---

@lru_cache(maxsize=32)
def get_arity(tuple_class: Type[AbstractTuple]) -> int:
    """Gets the arity (number of facts) for a given tuple class."""
    arity = TUPLE_TO_ARITY.get(tuple_class)
    if arity is None:
        raise TypeError(f"Class {tuple_class.__name__} is not a supported Tuple type.")
    return arity

def get_facts(t: AbstractTuple) -> List:
    """Extracts all facts from a tuple instance into a list."""
    # This direct-lookup approach is significantly faster than repeated hasattr checks.
    arity = get_arity(type(t))
    if arity == 1: return [t.fact_a]
    if arity == 2: return [t.fact_a, t.fact_b]
    if arity == 3: return [t.fact_a, t.fact_b, t.fact_c]
    if arity == 4: return [t.fact_a, t.fact_b, t.fact_c, t.fact_d]
    if arity == 5: return [t.fact_a, t.fact_b, t.fact_c, t.fact_d, t.fact_e]
    raise TypeError(f"Cannot get facts for unsupported tuple type: {type(t).__name__}")

def create_tuple_from_facts(facts: List) -> AbstractTuple:
    """Creates a tuple of the correct type based on the number of facts."""
    arity = len(facts)
    tuple_class = ARITY_TO_TUPLE.get(arity)
    if tuple_class is None:
        raise ValueError(f"Cannot create a tuple for arity {arity}. Supported arities are 1-5.")
    # Dynamically creates an instance, e.g., BiTuple(facts[0], facts[1])
    return tuple_class(*facts)

def combine_tuples(left: AbstractTuple, right: AbstractTuple) -> AbstractTuple:
    """Combines two tuples into a new, larger tuple."""
    combined_facts = get_facts(left) + get_facts(right)
    return create_tuple_from_facts(combined_facts)
