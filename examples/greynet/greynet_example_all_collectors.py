# main_example.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Type, Callable, List
from datetime import datetime, timedelta, timezone
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors
from greyjack.score_calculation.scores.SimpleScore import SimpleScore


# 1. Data Class Definitions (Facts)
# =================================

@greynet_fact
@dataclass()
class Sale:
    sale_id: str
    product_id: str
    customer_id: str
    price: float
    quantity: int
    timestamp: datetime

@greynet_fact
@dataclass()
class Shipment:
    order_id: str
    shipment_id: str
    shipment_no: int

@greynet_fact
@dataclass()
class Maintenance:
    machine_id: str
    start_time: datetime
    end_time: datetime

@greynet_fact
@dataclass()
class UserEvent:
    user_id: str
    event_type: str
    value: float  # e.g., transaction amount
    timestamp: datetime


# 2. Constraint and Collector Definitions
# =======================================

# Initialize the constraint builder
cb = ConstraintBuilder(name="collector_showcase", score_class=SimpleScore)

@cb.constraint("count_total_sales_per_product")
def count_collector_example():
    """Demonstrates: CountCollector
    Counts the number of sales transactions for each product. Penalizes if a product has more than 3 sales.
    """
    return (cb.for_each(Sale)
            .group_by(lambda s: s.product_id, Collectors.count())
            .filter(lambda product_id, count: count > 3)
            .penalize_simple(lambda product_id, count: count)
           )

@cb.constraint("sum_revenue_per_product")
def sum_collector_example():
    """Demonstrates: SumCollector
    Calculates the total revenue (price * quantity) for each product.
    """
    return (cb.for_each(Sale)
            .group_by(lambda s: s.product_id, Collectors.sum(lambda s: s.price * s.quantity))
            .filter(lambda product_id, total_revenue: total_revenue > 0)
            .penalize_simple(lambda product_id, total_revenue: 0) # Use penalty 0 to just report
           )

@cb.constraint("basic_price_stats_per_product")
def min_max_avg_collectors_example():
    """Demonstrates: MinCollector, MaxCollector, AvgCollector
    Finds the minimum, maximum, and average sale price for each product.
    """
    return (cb.for_each(Sale)
            .group_by(lambda s: s.product_id, Collectors.compose({
                "min_price": Collectors.min(lambda s: s.price),
                "max_price": Collectors.max(lambda s: s.price),
                "avg_price": Collectors.avg(lambda s: s.price)
            }))
            .filter(lambda product_id, stats: stats["max_price"] > 1.0)
            .penalize_simple(lambda product_id, stats: 0) # Reporting only
           )

@cb.constraint("advanced_price_stats_per_product")
def stddev_variance_collectors_example():
    """Demonstrates: StdDevCollector, VarianceCollector
    Calculates the standard deviation and variance of prices for each product.
    """
    return (cb.for_each(Sale)
            .group_by(lambda s: s.product_id, Collectors.compose({
                "price_stddev": Collectors.stddev(lambda s: s.price),
                "price_variance": Collectors.variance(lambda s: s.price)
            }))
            .filter(lambda product_id, stats: stats["price_stddev"] > 0)
            .penalize_simple(lambda product_id, stats: 0) # Reporting only
           )

@cb.constraint("list_of_sales_per_product")
def list_collector_example():
    """Demonstrates: ListCollector
    Collects all `Sale` objects for each product into a list.
    """
    return (cb.for_each(Sale)
            .group_by(lambda s: s.product_id, Collectors.to_list())
            .filter(lambda product_id, sales_list: len(sales_list) > 0)
            .penalize_simple(lambda product_id, sales_list: 0) # Reporting only
           )

@cb.constraint("set_of_customers_per_product")
def set_collector_example():
    """Demonstrates: SetCollector and MappingCollector
    Collects the unique set of customer IDs for each product.
    """
    return (cb.for_each(Sale)
            .group_by(
                lambda s: s.product_id,
                Collectors.mapping(
                    lambda s: s.customer_id, 
                    Collectors.to_set()
                )
            )
            .filter(lambda product_id, customer_set: len(customer_set) > 0)
            .penalize_simple(lambda product_id, customer_set: 0) # Reporting only
           )

@cb.constraint("distinct_list_of_customers_per_product")
def distinct_collector_example():
    """Demonstrates: DistinctCollector
    Collects a list of unique customer IDs for each product, preserving insertion order.
    """
    return (cb.for_each(Sale)
            .group_by(
                lambda s: s.product_id,
                Collectors.mapping(
                    lambda s: s.customer_id,
                    Collectors.distinct()
                )
            )
            .filter(lambda product_id, customer_list: len(customer_list) > 0)
            .penalize_simple(lambda product_id, customer_list: 0) # Reporting only
           )
           
@cb.constraint("count_high_quantity_sales")
def filtering_collector_example():
    """Demonstrates: FilteringCollector
    Counts only the sales where the quantity is greater than 2.
    """
    return (cb.for_each(Sale)
            .group_by(
                lambda s: s.product_id,
                Collectors.filtering(
                    lambda s: s.quantity > 2,
                    Collectors.count()
                )
            )
            .filter(lambda product_id, count: count > 0)
            .penalize_simple(lambda product_id, count: 0) # Reporting only
           )

# 3. Main Execution Block
# =======================

def run_demonstration():
    """Builds the session, inserts data, and prints the results."""
    
    # --- Sample Data ---
    now = datetime.now(timezone.utc)
    sales_data = [
        Sale("s1", "prod-a", "cust-1", 10.0, 1, now),
        Sale("s2", "prod-b", "cust-1", 25.5, 2, now + timedelta(seconds=1)),
        Sale("s3", "prod-a", "cust-2", 12.0, 5, now + timedelta(seconds=2)),
        Sale("s4", "prod-a", "cust-1", 11.5, 2, now + timedelta(seconds=3)),
        Sale("s5", "prod-b", "cust-3", 24.0, 1, now + timedelta(seconds=4)),
        Sale("s6", "prod-a", "cust-3", 12.5, 3, now + timedelta(seconds=5)),
    ]
    
    shipments_data = [
        Shipment("order-1", "sh-101", 1),
        Shipment("order-1", "sh-102", 2),
        Shipment("order-2", "sh-201", 1),
        Shipment("order-1", "sh-104", 4), # Gap in sequence
        Shipment("order-1", "sh-103", 3),
    ]

    maintenance_data = [
        Maintenance("m1", now, now + timedelta(hours=2)),
        Maintenance("m2", now, now + timedelta(hours=1)),
        Maintenance("m1", now + timedelta(hours=1), now + timedelta(hours=3)), # Overlaps with the first
        Maintenance("m1", now + timedelta(hours=4), now + timedelta(hours=5)), # Adjacent
    ]

    user_events_data = [
        UserEvent("u1", "tx", 100, now),
        UserEvent("u2", "tx", 150, now + timedelta(seconds=2)),
        UserEvent("u1", "tx", 50,  now + timedelta(seconds=8)),
        UserEvent("u3", "tx", 200, now + timedelta(seconds=11)), # New window
        UserEvent("u2", "tx", 300, now + timedelta(seconds=15)),
    ]

    # --- Build and Run Session ---
    session = cb.build()
    
    print("## [INITIAL STATE] Inserting all facts...")
    session.insert_batch(sales_data)
    session.insert_batch(shipments_data)
    session.insert_batch(maintenance_data)
    session.insert_batch(user_events_data)
    
    matches = session.get_constraint_matches()
    print_results(matches)

    # --- Demonstrate Retraction ---
    print("\n\n## [RETRACTION] Retracting one sale (s6) and one shipment (sh-103)...")
    sale_to_retract = sales_data[-1]  # Sale("s6", "prod-a", ...)
    shipment_to_retract = shipments_data[-1] # Shipment("order-1", "sh-103", 3)
    
    session.retract(sale_to_retract)
    session.retract(shipment_to_retract)

    matches_after_retract = session.get_constraint_matches()
    print("## Results after retraction:")
    print_results(matches_after_retract)
    
def print_results(matches):
    """Helper function to print constraint matches in a structured way."""
    if not matches:
        print("  No constraint matches found.")
        return

    for constraint_id, match_list in matches.items():
        print(f"\n### Constraint: `{constraint_id}`")
        print("-" * (len(constraint_id) + 18))
        for score_obj, match_tuple in match_list:
            facts = [f for f in [
                getattr(match_tuple, 'fact_a', None),
                getattr(match_tuple, 'fact_b', None),
            ] if f is not None]
            
            print(f"  - Match: {facts}")
            print(f"    Score: {score_obj}")
        print("-" * (len(constraint_id) + 18))


if __name__ == "__main__":
    run_demonstration() 

