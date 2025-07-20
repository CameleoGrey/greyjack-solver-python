from __future__ import annotations
from typing import Type, Callable
from datetime import timedelta, datetime

from .session import Session
from .streams.abstract_stream import AbstractStream
from .streams.stream import Stream
from .core.tuple import UniTuple, BiTuple
from .streams.scoring_stream import ScoringStream
from .constraint_factory import ConstraintFactory
from .common.joiner_type import JoinerType
from .function import Function
from .constraint import Constraint
from .constraint_weights import ConstraintWeights
from greyjack.score_calculation.scores.SimpleScore import SimpleScore

from .collectors.count_collector import CountCollector
from .collectors.sum_collector import SumCollector
from .collectors.list_collector import ListCollector
from .collectors.set_collector import SetCollector
from .collectors.distinct_collector import DistinctCollector
from .collectors.min_collector import MinCollector
from .collectors.max_collector import MaxCollector
from .collectors.avg_collector import AvgCollector
from .collectors.stddev_collector import StdDevCollector
from .collectors.variance_collector import VarianceCollector
from .collectors.composite_collector import CompositeCollector
from .collectors.mapping_collector import MappingCollector
from .collectors.filtering_collector import FilteringCollector
from .collectors.constraint_match_collector import ConstraintMatchCollector
from .constraint_tools.counting_bloom_filter import CountingBloomFilter



class ConstraintBuilder:
    def __init__(self, name: str = "default", score_class: Type = None, weights: ConstraintWeights = None):
        if score_class is None:
            score_class = SimpleScore
            
        self.factory = ConstraintFactory(name, score_class)
        self.score_class = score_class
        self.weights = weights if weights is not None else ConstraintWeights()
        
        if not hasattr(score_class, 'get_score_fields'):
            raise TypeError(f"The score class '{score_class.__name__}' must have a "
                            "static method called 'get_score_fields' that returns a list of its score field names.")
        
        self.score_fields = score_class.get_score_fields()

    def constraint(self, constraint_id: str, default_weight: float = 1.0):
        def decorator(func: Callable):
            self.weights.set_weight(constraint_id, default_weight)
            
            def constraint_def() -> ScoringStream:
                constraint_obj = func()

                if not isinstance(constraint_obj, Constraint):
                    raise TypeError(f"The function decorated by @constraint for '{constraint_id}' must end "
                                    "with a call to a penalize method (e.g., .penalize_hard(...)).")

                constraint_obj.constraint_id = constraint_id
                
                target_field = f"{constraint_obj.score_type}_score"
                if constraint_obj.score_type == "simple":
                    target_field = "simple_value"

                if target_field not in self.score_fields:
                    valid_types = [s.replace('_score', '').replace('_value', '') for s in self.score_fields]
                    raise ValueError(f"Score type '{constraint_obj.score_type}' is not valid for score class "
                                     f"'{self.score_class.__name__}'. Valid types are: {valid_types}")

                def impact_function(*facts):
                    base_penalty = constraint_obj.penalty_function(*facts)
                    dynamic_weight = self.weights.get_weight(constraint_id)
                    final_penalty = float(base_penalty) * dynamic_weight
                    
                    score_kwargs = {field: 0.0 for field in self.score_fields}
                    score_kwargs[target_field] = abs(final_penalty)
                    return self.score_class(**score_kwargs)

                final_stream = ScoringStream(
                    source_stream=constraint_obj.stream,
                    constraint_id=constraint_obj.constraint_id,
                    impact_function=impact_function
                )
                return final_stream

            self.factory.add_constraint(constraint_def)
            return func
        return decorator

    def for_each(self, fact_class) -> Stream[UniTuple]:
        """Starts a stream from a given data class."""
        return self.factory.from_(fact_class)
    
    def for_each_unique_pair(self, fact_class) -> Stream[BiTuple]:
        stream_1 = self.for_each(fact_class)
        stream_2 = self.for_each(fact_class)
        
        return stream_1.join(stream_2,
                            JoinerType.LESS_THAN,
                            lambda fact: fact.greynet_fact_id,
                            lambda fact: fact.greynet_fact_id)
        

    def build(self, **kwargs) -> Session:
        """
        Builds and returns the session.

        Args:
            debug (bool): If True, enables continuous tracing for the session's lifetime.
            **kwargs: Additional arguments for the session.
        """
        return self.factory.build_session(weights=self.weights, **kwargs)
    

class Collectors:
    """A namespace for convenient access to collector suppliers."""
    @staticmethod
    def count():
        return CountCollector

    @staticmethod
    def sum(mapping_function):
        class Wrapper(Function):
            def apply(self, value): return mapping_function(value)
        return lambda: SumCollector(Wrapper())

    @staticmethod
    def min(mapping_function: Callable):
        """Creates a collector that finds the minimum value from a group."""
        class Wrapper(Function):
            def apply(self, value): return mapping_function(value)
        return lambda: MinCollector(Wrapper())

    @staticmethod
    def max(mapping_function: Callable):
        """Creates a collector that finds the maximum value from a group."""
        class Wrapper(Function):
            def apply(self, value): return mapping_function(value)
        return lambda: MaxCollector(Wrapper())
        
    @staticmethod
    def avg(mapping_function: Callable):
        """Creates a collector that calculates the average of a group."""
        class Wrapper(Function):
            def apply(self, value): return mapping_function(value)
        return lambda: AvgCollector(Wrapper())

    @staticmethod
    def stddev(mapping_function: Callable):
        """Creates a collector that calculates the population standard deviation of a group."""
        class Wrapper(Function):
            def apply(self, value): return mapping_function(value)
        return lambda: StdDevCollector(Wrapper())
    
    @staticmethod
    def variance(mapping_function: Callable):
        """Creates a collector that calculates the population variance of a group."""
        class Wrapper(Function):
            def apply(self, value): return mapping_function(value)
        return lambda: VarianceCollector(Wrapper())

    @staticmethod
    def compose(collector_suppliers: dict) -> Callable:
        """
        Creates a composite collector to perform multiple aggregations at once.
        """
        return lambda: CompositeCollector(collector_suppliers)

    @staticmethod
    def to_list():
        return ListCollector
    
    @staticmethod
    def to_set():
        return SetCollector

    @staticmethod
    def distinct():
        return DistinctCollector
    
    @staticmethod
    def mapping(mapping_function: Callable, downstream_supplier: Callable):
        return lambda: MappingCollector(mapping_function, downstream_supplier)

    @staticmethod
    def filtering(predicate: Callable, downstream_supplier: Callable):
        return lambda: FilteringCollector(predicate, downstream_supplier)
        
    @staticmethod
    def to_constraint_matches():
        """
        A semantic alias for to_list(), used for collecting the facts
        that form a constraint match within a group_by operation.
        """
        return ConstraintMatchCollector
    
    @staticmethod
    def to_bloom_filter(estimated_items: int = 1000, false_positive_rate: float = 0.01):
        """
        Creates a collector that aggregates items into a CountingBloomFilter.
        """
        class BloomCollector:
            def __init__(self):
                self.bf = CountingBloomFilter(estimated_items, false_positive_rate)
            
            def insert(self, item):
                self.bf.add(item)
                return lambda: self.bf.remove(item)
            
            def result(self):
                return self.bf
            
            def is_empty(self):
                return len(self.bf) == 0
        return BloomCollector


class Patterns:
    """A helper class for defining common, complex constraint patterns."""
    def __init__(self, builder):
        self.builder = builder

    def overlapping_ranges(self, fact_class, group_key_function, start_func, end_func):
        """
        Creates a stream that finds pairs of facts of the same type that have
        overlapping ranges, grouped by a key.
        """
        return (self.builder.for_each(fact_class)
                .join(self.builder.for_each(fact_class),
                    JoinerType.EQUAL,
                    group_key_function,
                    group_key_function)
                .filter(lambda f1, f2: f1.greynet_fact_id < f2.greynet_fact_id)
                .filter(lambda f1, f2: max(start_func(f1), start_func(f2)) < min(end_func(f1), end_func(f2)))
        )
