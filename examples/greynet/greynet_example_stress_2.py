# ==============================================================================
#  Advanced Stress Test for the GreyJack Rule Engine
#  Scenario: Algorithmic Trading Compliance Monitoring
# ==============================================================================

import time
import random
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Set, Tuple, Any
from collections import defaultdict

# --- Imports from the GreyJack Rule Engine ---
# Assuming 'greyjack' package is available in the python path
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors
from greyjack.score_calculation.greynet.common.joiner_type import JoinerType
# Assuming this import is correct as per your project structure
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore

# ==============================================================================
#  2. Data Model Definitions
# ==============================================================================

@greynet_fact
@dataclass()
class Trader:
    id: int
    name: str
    desk: str
    risk_limit: float
    is_insider: bool = False

@greynet_fact
@dataclass()
class Security:
    ticker: str
    sector: str
    is_restricted: bool = False

@greynet_fact
@dataclass()
class Trade:
    id: int
    trader_id: int
    ticker: str
    quantity: int
    price: float
    timestamp: datetime
    side: str  # 'BUY' or 'SELL'

@greynet_fact
@dataclass()
class MarketNews:
    id: int
    related_tickers: Tuple[str, ...]
    headline: str
    timestamp: datetime
    is_material: bool = True

# ==============================================================================
#  3. Helper Functions for Complex Rule Logic
# ==============================================================================

def has_painting_the_tape_pattern(trades: List[Trade]) -> bool:
    """
    Checks a list of trades for a specific manipulative pattern.
    Pattern: Two small buys followed by a large sell in a short time frame.
    """
    if len(trades) < 3:
        return False
    sorted_trades = sorted(trades, key=lambda t: t.timestamp)

    for i in range(len(sorted_trades) - 2):
        window = sorted_trades[i:i+3]
        if (window[2].timestamp - window[0].timestamp) > timedelta(minutes=2):
            continue
        
        is_pattern = (
            window[0].side == 'BUY' and window[0].quantity < 100 and
            window[1].side == 'BUY' and window[1].quantity < 100 and
            window[2].side == 'SELL' and window[2].quantity > 500
        )
        if is_pattern:
            return True
    return False

def count_trades_in_windows(trades: List[Trade]) -> int:
    """
    Counts violations within a list of trades.
    A violation is > 2 trades in any 5-minute tumbling window.
    """
    window_size_sec = timedelta(minutes=5).total_seconds()
    total_violations = 0
    
    window_counts = defaultdict(int)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc).timestamp()
    
    for trade in trades:
        window_index = int((trade.timestamp.timestamp() - epoch) // window_size_sec)
        window_counts[window_index] += 1

    for count in window_counts.values():
        if count > 2:
            total_violations += (count - 2)
    
    return total_violations

# ==============================================================================
#  4. Intricate and Complex Constraint Definitions
# ==============================================================================

def define_advanced_constraints(builder: ConstraintBuilder):
    """
    Defines complex compliance rules for algorithmic trading.
    """

    # --- Rule 1: Market Manipulation ("Painting the Tape") ---
    @builder.constraint("market_manipulation_painting_the_tape")
    def painting_the_tape():
        return builder.for_each(Trade) \
            .group_by(
                lambda trade: (trade.trader_id, trade.ticker),
                Collectors.to_list()
            ) \
            .filter(
                lambda key, trades: has_painting_the_tape_pattern(trades)
            ) \
            .penalize_hard(10000)


    # --- Rule 2: Exceeding Daily Risk Limits ---
    @builder.constraint("trader_exceeds_daily_risk_limit")
    def trader_risk_limit():
        daily_trade_volumes = builder.for_each(Trade) \
            .group_by(
                lambda trade: (trade.trader_id, trade.timestamp.date()),
                Collectors.compose({
                    'total_volume': Collectors.sum(lambda t: t.price * t.quantity),
                    'trade_count': Collectors.count()
                })
            )

        # FIXED: The join is reversed. We start from the aggregated stream
        # and join the Trader facts to it. This uses a different node
        # that preserves all necessary data.
        return daily_trade_volumes \
            .join(builder.for_each(Trader),
                  JoinerType.EQUAL,
                  # Left key func: extracts trader_id from the group key
                  lambda key, result: key[0],
                  # Right key func: extracts trader_id from the trader object
                  lambda trader: trader.id
            ) \
            .filter(
                # The lambda now receives (key, result_dict, trader).
                lambda key, result_dict, trader: result_dict['total_volume'] > trader.risk_limit
            ) \
            .penalize_hard(
                # The penalty lambda also receives all three facts.
                lambda key, result_dict, trader: (result_dict['total_volume'] - trader.risk_limit) / 1000
            )


    # --- Rule 3: Potential Insider Trading ---
    @builder.constraint("potential_insider_trading")
    def insider_trading():
        insider_trades = builder.for_each(Trader)\
            .filter(lambda trader: trader.is_insider)\
            .join(builder.for_each(Trade),
                JoinerType.EQUAL,
                lambda trader: trader.id,
                lambda trade: trade.trader_id
            )

        return insider_trades.join(builder.for_each(MarketNews),
                JoinerType.EQUAL,
                lambda trader, trade: trade.ticker,
                lambda news: news.related_tickers[0] if news.related_tickers else None
            ).filter(lambda trader, trade, news:
                news.is_material and
                timedelta(minutes=1) < (news.timestamp - trade.timestamp) < timedelta(hours=1)
            ).penalize_hard(50000)


    # --- Rule 4: Restricted Security Trading Bursts ---
    @builder.constraint("restricted_security_trading_burst")
    def restricted_trading_burst():
        restricted_trades = builder.for_each(Trade) \
            .if_exists(
                builder.for_each(Security).filter(lambda s: s.is_restricted),
                lambda trade: trade.ticker,
                lambda sec: sec.ticker
            )
        
        return restricted_trades.group_by(
            lambda trade: trade.ticker,
            Collectors.to_list()
        ).filter(
            lambda ticker, trades: count_trades_in_windows(trades) > 0
        ).penalize_soft(
            lambda ticker, trades: count_trades_in_windows(trades) * 50
        )

# ==============================================================================
#  5. Data Generation
# ==============================================================================

def generate_advanced_data(num_traders, num_securities, num_trades) -> Dict[str, list]:
    """Generates a large, randomized dataset with specific patterns for detection."""
    print("Generating advanced test data with specific patterns...")
    start_time = datetime.now(timezone.utc) - timedelta(days=1)

    # --- Generate Base Entities ---
    traders = [
        Trader(
            id=i, name=f"Trader_{i}", desk=random.choice(['Equities', 'FX', 'Derivatives']),
            risk_limit=random.uniform(5_000_000, 20_000_000),
            is_insider= (i % 20 == 0) # 5% of traders are insiders
        ) for i in range(num_traders)
    ]
    securities = [
        Security(
            ticker=f"SEC_{i}", sector=random.choice(['Tech', 'Health', 'Finance']),
            is_restricted=(i % 15 == 0) # ~6.7% of securities are restricted
        ) for i in range(num_securities)
    ]
    
    facts: Dict[str, list] = {"traders": traders, "securities": securities, "trades": [], "news": []}
    trade_id_counter = 0

    # --- Inject Pattern: Painting the Tape ---
    victim_security = securities[1]
    manipulator_trader = traders[1]
    print(f"  Injecting 'Painting the Tape' pattern for {manipulator_trader.name} on {victim_security.ticker}...")
    base_ts = start_time + timedelta(hours=1)
    facts["trades"].append(Trade(trade_id_counter, manipulator_trader.id, victim_security.ticker, 50, 100.0, base_ts, 'BUY')); trade_id_counter+=1
    facts["trades"].append(Trade(trade_id_counter, manipulator_trader.id, victim_security.ticker, 60, 100.5, base_ts + timedelta(seconds=30), 'BUY')); trade_id_counter+=1
    facts["trades"].append(Trade(trade_id_counter, manipulator_trader.id, victim_security.ticker, 600, 101.0, base_ts + timedelta(seconds=90), 'SELL')); trade_id_counter+=1

    # --- Inject Pattern: Risk Limit Breach ---
    risky_trader = traders[2]
    # Set a specific, predictable risk limit to breach
    risky_trader = Trader(id=risky_trader.id, name=risky_trader.name, desk=risky_trader.desk, risk_limit=24_000_000, is_insider=risky_trader.is_insider)
    facts["traders"][2] = risky_trader # Replace the old trader fact
    print(f"  Injecting 'Risk Limit Breach' pattern for {risky_trader.name} (Limit: {risky_trader.risk_limit})...")
    # 5 trades of 5M each = 25M total volume, which is > 24M limit
    for i in range(5):
        facts["trades"].append(Trade(trade_id_counter, risky_trader.id, securities[10].ticker, 10000, 500.0, start_time + timedelta(hours=2, minutes=i), 'BUY')); trade_id_counter+=1

    # --- Inject Pattern: Insider Trading ---
    insider_trader = next(t for t in traders if t.is_insider)
    insider_security = securities[5]
    print(f"  Injecting 'Insider Trading' pattern for {insider_trader.name} on {insider_security.ticker}...")
    trade_ts = start_time + timedelta(hours=3)
    news_ts = trade_ts + timedelta(minutes=30)
    facts["trades"].append(Trade(trade_id_counter, insider_trader.id, insider_security.ticker, 5000, 250.0, trade_ts, 'BUY')); trade_id_counter+=1
    facts["news"].append(MarketNews(0, (insider_security.ticker,), "BREAKING: SEC_5 to be acquired by major rival!", news_ts, True))

    # --- Inject Pattern: Restricted Trading Burst ---
    restricted_sec = next(s for s in securities if s.is_restricted)
    burst_trader = traders[3]
    print(f"  Injecting 'Restricted Trading Burst' on {restricted_sec.ticker}...")
    burst_ts = start_time + timedelta(hours=4)
    # 4 trades in the same 5-min window will trigger a penalty of (4-2)=2 * 50
    for i in range(4):
        facts["trades"].append(Trade(trade_id_counter, burst_trader.id, restricted_sec.ticker, 100, 50.0, burst_ts + timedelta(minutes=i), 'SELL')); trade_id_counter+=1

    # --- Generate Random "Noise" Trades ---
    print(f"  Generating {num_trades} random noise trades...")
    for _ in range(num_trades):
        trader = random.choice(traders)
        security = random.choice(securities)
        ts = start_time + timedelta(seconds=random.randint(0, 86400))
        facts["trades"].append(Trade(
            id=trade_id_counter, trader_id=trader.id, ticker=security.ticker,
            quantity=random.randint(10, 1000), price=random.uniform(10, 1000),
            timestamp=ts, side=random.choice(['BUY', 'SELL'])
        )); trade_id_counter+=1

    return facts

# ==============================================================================
#  6. Main Test Runner
# ==============================================================================

def main():
    """Main function to run the stress test and report results."""
    
    # --- Configuration ---
    NUM_TRADERS = 100
    NUM_SECURITIES = 2000
    NUM_TRADES = 100_000
    
    print("### Starting Advanced Rule Engine Stress Test ###")
    
    # 1. Setup Phase & Initial State
    tracemalloc.start()
    
    time_start_setup = time.perf_counter()
    builder = ConstraintBuilder(name="adv-stress-test", score_class=HardSoftScore)
    define_advanced_constraints(builder)
    session = builder.build()
    time_end_setup = time.perf_counter()
    
    # 2. Data Generation Phase
    time_start_data = time.perf_counter()
    data = generate_advanced_data(NUM_TRADERS, NUM_SECURITIES, NUM_TRADES)
    all_facts = data["traders"] + data["securities"] + data["trades"] + data["news"]
    time_end_data = time.perf_counter()

    # 3. Processing Phase
    print("\nInserting facts and processing rules...")
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

    # Display Report using Markdown Table
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
        print(f"  - `{constraint_id}`: {len(match_list)} matches found.")

if __name__ == "__main__":
    main()

