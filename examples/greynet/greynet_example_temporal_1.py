import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from collections import deque
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors
from greyjack.score_calculation.greynet.common.joiner_type import JoinerType


# TODO: Fix temporal, sequential features
# TODO: Add debug, tracing for temporal, sequential features


@greynet_fact
@dataclass
class UserEvent:
    user_id: str
    timestamp: datetime

@greynet_fact
@dataclass
class FundDeposit(UserEvent):
    amount: float
    currency: str

@greynet_fact
@dataclass
class TradeOrder(UserEvent):
    amount: float
    asset_pair: str
    order_type: str

@greynet_fact
@dataclass
class FundWithdrawal(UserEvent):
    amount: float
    to_address: str

@greynet_fact
@dataclass
class AccountFlag(UserEvent):
    reason: str
    expires_at: datetime


def find_deposit_withdrawal_sequences(user_id, events):
    pattern_steps = [
        lambda fact: isinstance(fact, FundDeposit) and fact.amount >= 10000,
        lambda fact: isinstance(fact, FundWithdrawal) and fact.amount >= 9000
    ]
    within_delta = timedelta(hours=24)
    sorted_events = sorted(events, key=lambda e: e.timestamp)
    
    for i in range(len(sorted_events)):
        if pattern_steps[0](sorted_events[i]):
            for j in range(i + 1, len(sorted_events)):
                event1 = sorted_events[i]
                event2 = sorted_events[j]
                if event2.timestamp - event1.timestamp > within_delta:
                    break
                if pattern_steps[1](event2):
                    yield [event1, event2]

def find_high_velocity_windows_for_user(withdrawals: list):
    """
    Applies a continuous sliding window to a single user's sorted withdrawals
    to find periods of high activity.
    """
    if not withdrawals:
        return

    window_size = timedelta(hours=1)
    threshold = 100000
    
    sorted_w = sorted(withdrawals, key=lambda w: w.timestamp)
    
    window = deque()
    current_sum = 0.0
    yielded_violations = set()

    for w in sorted_w:
        window.append(w)
        current_sum += w.amount
        
        while w.timestamp - window[0].timestamp > window_size:
            removed_fact = window.popleft()
            current_sum -= removed_fact.amount
            
        if current_sum > threshold:
            violation_key = frozenset(window)
            if violation_key not in yielded_violations:
                yield list(window)
                yielded_violations.add(violation_key)


class FraudDetection:
    def __init__(self):
        self.builder = ConstraintBuilder(name="FraudDetectionSystem", score_class=SimpleScore)
        self.define_constraints()

    def define_constraints(self):
        """Uses the constraint decorator to define all detection rules."""

        # Rule 1: High-Frequency Trading
        @self.builder.constraint("HIGH_FREQ_TRADING", default_weight=1.0)
        def high_frequency_trading():
            five_min_bucket = lambda ts: int(ts.timestamp() // 300)
            return (self.builder.for_each(TradeOrder)
                .group_by(
                    group_key_function=lambda trade: (trade.user_id, five_min_bucket(trade.timestamp)),
                    collector_supplier=Collectors.to_list()
                )
                .filter(lambda group_key, trades: len(trades) > 50)
                .penalize_simple(lambda group_key, trades: (len(trades) - 50) * 10)
            )

        # Rule 2: Suspicious Deposit -> Withdrawal Sequence
        @self.builder.constraint("SUSPICIOUS_SEQUENCE", default_weight=1.0)
        def suspicious_deposit_withdrawal_sequence():
            return (self.builder.for_each(UserEvent)
                .group_by(
                    group_key_function=lambda event: event.user_id,
                    collector_supplier=Collectors.to_list()
                )
                .flat_map(lambda user_id, events: find_deposit_withdrawal_sequences(user_id, events))
                .penalize_simple(5000)
            )

        @self.builder.constraint("HIGH_VELOCITY_WITHDRAWALS", default_weight=1.0)
        def high_velocity_withdrawals():
            return (self.builder.for_each(FundWithdrawal)
                .group_by(
                    group_key_function=lambda w: w.user_id,
                    collector_supplier=Collectors.to_list()
                )
                .flat_map(lambda user_id, withdrawals: find_high_velocity_windows_for_user(withdrawals))
                .penalize_simple(lambda facts: sum(w.amount for w in facts) - 100000)
            )

        # Rule 4: Trading While Under Account Flag (Unchanged)
        @self.builder.constraint("TRADING_WHILE_FLAGGED", default_weight=1.0)
        def trading_while_flagged():
            high_value_trades = self.builder.for_each(TradeOrder).filter(lambda t: t.amount > 20000)
            account_flags = self.builder.for_each(AccountFlag)
            return (high_value_trades
                .join(account_flags,
                      JoinerType.EQUAL,
                      left_key_func=lambda trade: trade.user_id,
                      right_key_func=lambda flag: flag.user_id
                )
                .filter(lambda trade, flag: flag.timestamp <= trade.timestamp <= flag.expires_at)
                .penalize_simple(1500)
            )

    def get_session(self):
        return self.builder.build()


def run_simulation():
    print("### Setting up Fraud Detection System with Corrected Logic ###")
    fraud_system = FraudDetection()
    session = fraud_system.get_session()
    
    user_A = "user-Alice-123"
    user_B = "user-Bob-456"
    user_C = "user-Charlie-789"
    
    start_time = datetime.now(timezone.utc)
    events = []

    print("\n -> Generating data for [TRADING_WHILE_FLAGGED]")
    events.append(AccountFlag(user_id=user_A, timestamp=start_time, reason="KYC_REVIEW", expires_at=start_time + timedelta(days=7)))
    events.append(TradeOrder(user_id=user_A, timestamp=start_time + timedelta(hours=1), amount=25000, asset_pair="BTC/USD", order_type="SELL"))

    print(" -> Generating data for [SUSPICIOUS_SEQUENCE]")
    events.append(FundDeposit(user_id=user_B, timestamp=start_time + timedelta(minutes=10), amount=15000, currency="USDC"))
    events.append(FundWithdrawal(user_id=user_B, timestamp=start_time + timedelta(hours=5), amount=14950, to_address="0xabc...def"))
    
    print(" -> Generating data for [HIGH_FREQ_TRADING]")
    for i in range(55):
        events.append(TradeOrder(user_id=user_C, timestamp=start_time + timedelta(seconds=i*2), amount=100, asset_pair="ETH/USD", order_type="BUY"))

    print(" -> Generating data for [HIGH_VELOCITY_WITHDRAWALS]")
    events.append(FundWithdrawal(user_id=user_A, timestamp=start_time + timedelta(minutes=30), amount=60000, to_address="0x123...456"))
    events.append(FundWithdrawal(user_id=user_B, timestamp=start_time + timedelta(minutes=45), amount=45000, to_address="0x789...012"))

    print("\n### Inserting Events into Session ###")
    session.insert_batch(events)
    
    print("\n### Calculating Initial Score ###")
    print("Expected Score: 50 (HFT) + 10000 (2x Sequence) + 0 (High Velocity) + 1500 (Flagged) = 11550")
    initial_score = session.get_score()
    print(f"Actual Initial Total Score: {initial_score.simple_value}")

    print("\n### Retrieving Constraint Matches ###")
    matches = session.get_constraint_matches()
    
    print("\n```mermaid")
    print("graph TD")
    print("    subgraph Detected Violations")
    if not matches:
        print("        No Violations Detected")
    for constraint_id, violations in matches.items():
        print(f"        {constraint_id} -- has {len(violations)} violation(s) --> V_{constraint_id}")
        for i, violation in enumerate(violations):
            score_object, _ = violation
            score_val = score_object.simple_value
            fact_summary = f"Penalty: {score_val:.2f}"
            print(f"        V_{constraint_id} -- \"{fact_summary}\" --> V_{constraint_id}_{i}")
    print("    end")
    print("```")

    print("\n### Demonstrating Dynamic Weight Update ###")
    print(" -> Increasing weight of 'TRADING_WHILE_FLAGGED' from 1.0 to 3.0")
    session.update_constraint_weight("TRADING_WHILE_FLAGGED", 3.0)
    
    updated_score = session.get_score()
    print(f"Expected Updated Score: 11550 - 1500 + (1500 * 3) = 14550")
    print(f"Actual Updated Total Score: {updated_score.simple_value}")
    print(f"Score increased by: {updated_score.simple_value - initial_score.simple_value:.2f}")


if __name__ == "__main__":
    run_simulation()
