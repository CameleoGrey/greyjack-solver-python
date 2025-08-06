import time
import random
import tracemalloc
from dataclasses import dataclass
from typing import List, Dict, Set

# --- Imports using the full, explicit path as requested ---
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors, JoinerType
from greyjack.score_calculation.scores.SimpleScore import SimpleScore

# --- Data Definitions ---

@greynet_fact
@dataclass()
class Customer:
    id: int
    risk_level: str  # 'low', 'medium', 'high'
    status: str      # 'active', 'inactive'

@greynet_fact
@dataclass()
class Transaction:
    id: int
    customer_id: int
    amount: float
    location: str

@greynet_fact
@dataclass()
class SecurityAlert:
    location: str
    severity: int    # 1 to 5

# --- Constraint Definitions ---

def define_constraints(builder: ConstraintBuilder):
    """
    Defines a set of rules to stress test various engine capabilities.
    """
    
    # Constraint 1: Simple filter for high-value transactions.
    @builder.constraint("high_value_transaction")
    def high_value_transaction():
        return builder.for_each(Transaction)\
            .filter(lambda tx: tx.amount > 45000)\
            .penalize_simple(lambda tx: tx.amount / 1000)

    # Constraint 2: Group transactions by customer and check for excessive activity.
    @builder.constraint("excessive_transactions_per_customer")
    def excessive_transactions():
        return builder.for_each(Transaction)\
            .group_by(lambda tx: tx.customer_id, Collectors.count())\
            .filter(lambda cid, count: count > 25)\
            .penalize_simple(lambda cid, count: (count - 25) * 10)

    # Constraint 3: Join transactions with security alerts on location.
    @builder.constraint("transaction_in_alerted_location")
    def suspicious_location_tx():
        return builder.for_each(Transaction)\
            .join(builder.for_each(SecurityAlert), 
                  JoinerType.EQUAL, 
                  lambda tx: tx.location, 
                  lambda alert: alert.location)\
            .penalize_simple(lambda tx, alert: 100 * alert.severity)

    # Constraint 4: Join to find transactions from inactive customers.
    @builder.constraint("inactive_customer_transaction")
    def inactive_customer_tx():
        return builder.for_each(Customer)\
            .filter(lambda c: c.status == 'inactive')\
            .join(builder.for_each(Transaction), 
                  JoinerType.EQUAL, 
                  lambda c: c.id, 
                  lambda tx: tx.customer_id)\
            .penalize_simple(500)

    # Constraint 5: Complex rule using if_not_exists.
    # Penalize if a high-risk customer has a transaction in a location
    # that does NOT have a security alert.
    @builder.constraint("high_risk_transaction_without_alert")
    def high_risk_no_alert():
        return builder.for_each(Customer)\
            .filter(lambda c: c.risk_level == 'high')\
            .join(builder.for_each(Transaction), 
                  JoinerType.EQUAL, 
                  lambda c: c.id, 
                  lambda tx: tx.customer_id)\
            .if_not_exists(
                SecurityAlert,
                left_key=lambda c, tx: tx.location,
                right_key=lambda alert: alert.location
            )\
            .penalize_simple(1000)


# --- Data Generation ---

def generate_data(num_customers: int, num_transactions: int, num_locations: int) -> Dict[str, list]:
    """Generates a large, randomized dataset for testing."""
    print("Generating test data...")
    locations = [f"location_{i}" for i in range(num_locations)]
    
    customers = [
        Customer(
            id=i,
            risk_level=random.choice(['low', 'medium', 'high']),
            status=random.choices(['active', 'inactive'], weights=[0.95, 0.05], k=1)[0]
        ) for i in range(num_customers)
    ]
    
    transactions = [
        Transaction(
            id=i,
            customer_id=random.randint(0, num_customers - 1),
            amount=random.uniform(1.0, 50000.0),
            location=random.choice(locations)
        ) for i in range(num_transactions)
    ]
    
    # Create alerts for a subset of locations
    alerted_locations = random.sample(locations, k=max(1, num_locations // 4))
    alerts = [
        SecurityAlert(
            location=loc,
            severity=random.randint(1, 5)
        ) for loc in alerted_locations
    ]
    
    return {"customers": customers, "transactions": transactions, "alerts": alerts}

# --- Main Test Runner ---

def main():
    """Main function to run the stress test and report results."""
    
    # --- Configuration ---
    NUM_CUSTOMERS = 10_000
    NUM_TRANSACTIONS = 10_000_000
    NUM_LOCATIONS = 1_000
    
    print("### Starting Rule Engine Stress Test (Windows Compatible) ###")
    
    # 1. Setup Phase & Initial State
    tracemalloc.start()
    
    time_start_setup = time.perf_counter()
    builder = ConstraintBuilder(name="stress-test-session", score_class=SimpleScore)
    define_constraints(builder)
    session = builder.build()
    time_end_setup = time.perf_counter()
    
    # 2. Data Generation Phase
    time_start_data = time.perf_counter()
    data = generate_data(NUM_CUSTOMERS, NUM_TRANSACTIONS, NUM_LOCATIONS)
    all_facts = data["customers"] + data["transactions"] + data["alerts"]
    time_end_data = time.perf_counter()

    # 3. Processing Phase
    print("Inserting facts and processing rules...")
    time_start_processing = time.perf_counter()
    session.insert_batch(all_facts)
    final_score = session.get_score()
    matches = session.get_constraint_matches()
    time_end_processing = time.perf_counter()
    
    # 4. Get Memory Snapshot
    mem_current, mem_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # 5. Reporting
    print("\n--- Stress Test Results ---")
    
    # Time Metrics
    setup_duration = time_end_setup - time_start_setup
    data_gen_duration = time_end_data - time_start_data
    processing_duration = time_end_processing - time_start_processing
    total_duration = time_end_processing - time_start_setup

    # Performance Metrics
    total_facts = len(all_facts)
    facts_per_second = total_facts / processing_duration if processing_duration > 0 else float('inf')

    # Display Report using Markdown
    print("\n#### Performance Summary")
    print(f"| Metric                         | Value               |")
    print(f"|--------------------------------|---------------------|")
    print(f"| Total Facts Processed          | {total_facts:,}         |")
    print(f"| Setup Time (Build Network)     | {setup_duration:.4f} s      |")
    print(f"| Data Generation Time           | {data_gen_duration:.4f} s      |")
    print(f"| **Processing Time (Insert+Flush)** | **{processing_duration:.4f} s**      |")
    print(f"| Total Time                     | {total_duration:.4f} s      |")
    print(f"| **Throughput**                 | **{facts_per_second:,.2f} facts/sec** |")

    print("\n#### Memory Usage Summary (via tracemalloc)")
    print(f"| Metric                         | Value               |")
    print(f"|--------------------------------|---------------------|")
    print(f"| Final Memory Usage             | {mem_current / 1024**2:.2f} MB        |")
    print(f"| **Peak Memory Usage**          | **{mem_peak / 1024**2:.2f} MB**        |")


    print("\n#### Engine Output")
    print(f"- **Final Score:** {final_score}")
    print(f"- **Total Constraint Matches:** {sum(len(v) for v in matches.values())}")
    for constraint_id, match_list in sorted(matches.items()):
        print(f"  - `{constraint_id}`: {len(match_list)} matches")

if __name__ == "__main__":
    # To run this script, place it in a location where it can import the
    # 'greyjack' package correctly, as per your project structure.
    main()
