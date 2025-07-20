# greynet/core/tuple_pool.py
from __future__ import annotations
from collections import defaultdict, deque
from typing import Type, TypeVar

from ..core.tuple import AbstractTuple

T = TypeVar('T', bound=AbstractTuple)


class TuplePool:
    """
    Manages pools of tuple objects to reduce memory allocation overhead.

    This class maintains a separate pool (a deque) for each tuple type.
    When a tuple is requested, it tries to retrieve one from the pool.
    If the pool is empty, a new tuple is created. When a tuple is
    no longer needed, it's released back to the pool for reuse.
    """
    def __init__(self):
        self._pools: defaultdict[Type[T], deque[T]] = defaultdict(deque)

    def acquire(self, tuple_class: Type[T], **kwargs) -> T:
        """
        Acquires a tuple instance, either by reusing one from the pool or
        creating a new one.

        Args:
            tuple_class: The class of the tuple to acquire (e.g., UniTuple).
            **kwargs: The initial attributes for the tuple (e.g., fact_a).

        Returns:
            An initialized instance of the requested tuple class.
        """
        pool = self._pools[tuple_class]
        if pool:
            # Reuse an existing tuple from the pool
            tuple_instance = pool.popleft()
            # Re-initialize its attributes
            for key, value in kwargs.items():
                setattr(tuple_instance, key, value)
            return tuple_instance
        else:
            # Create a new tuple if the pool is empty
            return tuple_class(**kwargs)

    def release(self, tuple_instance: T):
        """
        Releases a tuple back to the pool for future reuse.

        The tuple is reset to a clean state before being added back.

        Args:
            tuple_instance: The tuple object to release.
        """
        tuple_class = type(tuple_instance)
        # Ensure the tuple is cleaned before pooling
        tuple_instance.reset()
        self._pools[tuple_class].append(tuple_instance)

    def stats(self) -> dict[str, int]:
        """Returns the current size of each pool for diagnostics."""
        return {
            cls.__name__: len(pool)
            for cls, pool in self._pools.items()
        }
