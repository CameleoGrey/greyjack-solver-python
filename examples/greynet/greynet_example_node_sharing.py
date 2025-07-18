import time
import random
from dataclasses import dataclass
import tracemalloc

# Assume all provided GreyJack files are in the classpath
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder
from greyjack.score_calculation.scores.SimpleScore import SimpleScore

# --- 1. Setup & Data Models ---

@greynet_fact
@dataclass
class Transaction:
    transaction_id: str
    amount: float
    country_code: str

def format_bytes(num_bytes: int) -> str:
    """Formats a byte count into a human-readable string (KB, MB, etc.)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"

# --- SOLUTION: Callable class to ensure unique node identity ---
class AmountThresholdFilter:
    def __init__(self, threshold: float):
        self.threshold = threshold

    def __call__(self, t: Transaction) -> bool:
        return t.amount > self.threshold
    
    # The __eq__ and __hash__ methods are critical for the engine
    # to correctly distinguish between different filter instances.
    def __eq__(self, other):
        return isinstance(other, AmountThresholdFilter) and self.threshold == other.threshold

    def __hash__(self):
        return hash((self.__class__, self.threshold))

# --- 2. Rule Generation Logic ---

def create_rules(builder: ConstraintBuilder, num_rules: int, with_sharing: bool):
    """
    Programmatically generates and adds rules to a ConstraintBuilder.
    """
    print(f"Generating {num_rules} rules {'with' if with_sharing else 'without'} node sharing...")
    
    for i in range(num_rules):
        constraint_id = f"high_value_tx_{i}"
        
        if with_sharing:
            # All rules share the exact same filter condition.
            @builder.constraint(constraint_id, default_weight=1.0)
            def shared_rule():
                return (builder.for_each(Transaction)
                               .filter(lambda t: t.amount > 5000)
                               .penalize_simple(lambda t: t.amount))
        else:
            # Each rule now gets a unique filter object with its own state.
            # This forces the engine to create a new AlphaNode for each rule.
            def create_unique_rule(rule_index):
                # Create a unique, stateful filter instance for each rule
                unique_filter = AmountThresholdFilter(5000 + rule_index)

                @builder.constraint(f"high_value_tx_unique_{rule_index}", default_weight=1.0)
                def unique_rule():
                    return (builder.for_each(Transaction)
                                   .filter(unique_filter) # Use the unique filter object
                                   .penalize_simple(lambda t: t.amount))
                return unique_rule
            
            create_unique_rule(i)

# --- 3. Benchmarking Harness (Unchanged) ---
def run_benchmark(num_rules: int, num_facts: int, with_sharing: bool):
    scenario_name = "With Node Sharing" if with_sharing else "Without Node Sharing"
    print(f"\n----- Running Benchmark: {scenario_name} -----")
    
    builder = ConstraintBuilder(name=f"scenario_{'shared' if with_sharing else 'unique'}", score_class=SimpleScore)
    
    start_build_time = time.perf_counter()
    create_rules(builder, num_rules, with_sharing)
    session = builder.build()
    end_build_time = time.perf_counter()
    build_duration = end_build_time - start_build_time
    
    tracemalloc.start()
    facts = [
        Transaction(transaction_id=str(i), amount=random.uniform(1, 10000), country_code="US")
        for i in range(num_facts)
    ]
    session = builder.build() 
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    start_insert_time = time.perf_counter()
    session.insert_batch(facts)
    session.flush()
    end_insert_time = time.perf_counter()
    insert_duration = end_insert_time - start_insert_time
    
    score = session.get_score()
    print(f"Score: {score.simple_value}")

    return {
        "Scenario": scenario_name,
        "Build Time (s)": f"{build_duration:.4f}",
        "Insertion Time (s)": f"{insert_duration:.4f}",
        "Peak Memory": format_bytes(peak)
    }

if __name__ == '__main__':
    NUM_RULES = 100
    NUM_FACTS = 50000

    results_no_sharing = run_benchmark(NUM_RULES, NUM_FACTS, with_sharing=False)
    results_with_sharing = run_benchmark(NUM_RULES, NUM_FACTS, with_sharing=True)
    
    print("\n\n--- BENCHMARK RESULTS ---")
    print(f"Configuration: {NUM_RULES} rules, {NUM_FACTS} facts.")
    print("---------------------------------------------------------------------")
    print(f"| {'Scenario':<25} | {'Build Time (s)':<15} | {'Insertion Time (s)':<20} | {'Peak Memory':<15} |")
    print("---------------------------------------------------------------------")
    print(f"| {results_no_sharing['Scenario']:<25} | {results_no_sharing['Build Time (s)']:<15} | {results_no_sharing['Insertion Time (s)']:<20} | {results_no_sharing['Peak Memory']:<15} |")
    print(f"| {results_with_sharing['Scenario']:<25} | {results_with_sharing['Build Time (s)']:<15} | {results_with_sharing['Insertion Time (s)']:<20} | {results_with_sharing['Peak Memory']:<15} |")
    print("---------------------------------------------------------------------")
