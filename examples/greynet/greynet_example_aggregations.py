# In main_example_fixed.py, after the existing code

# --- 4. New Usage Example for Aggregations ---
from dataclasses import dataclass
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors
from greyjack.score_calculation.scores.SimpleScore import SimpleScore

@greynet_fact
@dataclass()
class SalesTransaction:
    region: str
    amount: float

builder = ConstraintBuilder(name="temporal-security", score_class=SimpleScore)
# Define a constraint to analyze sales data per region.
# We use a penalty of 0 because the goal is data extraction, not scoring.
@builder.constraint("Sales Regional Analysis")
def sales_analysis():
    return (
        builder.for_each(SalesTransaction)
            .group_by(
                lambda tx: tx.region,
                Collectors.compose({
                    "min_sale":    Collectors.min(lambda tx: tx.amount),
                    "max_sale":    Collectors.max(lambda tx: tx.amount),
                    "avg_sale":    Collectors.avg(lambda tx: tx.amount),
                    "stddev_sale": Collectors.stddev(lambda tx: tx.amount),
                    "total_sales": Collectors.sum(lambda tx: tx.amount),
                    "num_sales":   Collectors.count()
                })
            )
            .penalize_simple(0)
    )

# --- Execute the new analysis ---
print("\n" + "="*50)
print("--- Starting Sales Aggregation Example ---")
print("="*50)

# Re-use the same builder to create a new session if needed, or add to the existing one.
# For a clean test, we'll build it again.
sales_session = builder.build()

transactions = [
    SalesTransaction("North", 110.0),
    SalesTransaction("North", 150.0),
    SalesTransaction("North", 195.5),
    SalesTransaction("South", 500.0),
    SalesTransaction("South", 600.0),
    SalesTransaction("West", 300.0),
]

sales_session.insert_batch(transactions)
sales_session.flush()

print("\n--- Sales Aggregation Results ---")
matches = sales_session.get_constraint_matches()
for constraint_id, violations in matches.items():
    if constraint_id == "Sales Regional Analysis":
        print(f"\nAnalysis: '{constraint_id}'")
        # Sort results by region for consistent output
        sorted_violations = sorted(violations, key=lambda v: v[1].fact_a)
        for _, facts_tuple in sorted_violations:
            region = facts_tuple.fact_a
            stats = facts_tuple.fact_b
            print(f"  - Region: {region}")
            print(f"    - Count:       {stats['num_sales']}")
            print(f"    - Total Sales: ${stats['total_sales']:.2f}")
            print(f"    - Average Sale:  ${stats['avg_sale']:.2f}")
            print(f"    - Min Sale:      ${stats['min_sale']:.2f}")
            print(f"    - Max Sale:      ${stats['max_sale']:.2f}")
            print(f"    - Std Dev:     ${stats['stddev_sale']:.2f}")

print("\n--- Sales Example Complete ---")
