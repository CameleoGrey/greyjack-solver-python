from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Union

# Assuming all provided files are in a structured 'greyjack' directory
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors
from greyjack.score_calculation.greynet.common.joiner_type import JoinerType
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore

# TODO: Fix temporal, sequential features
# TODO: Add debug, tracing for temporal, sequential features

# --- Data Models ---

@greynet_fact
@dataclass()
class LoginAttempt:
    user: str
    ip_address: str
    timestamp: datetime
    successful: bool

@greynet_fact
@dataclass()
class FileAccess:
    user: str
    file_path: str
    operation: str  # 'read', 'write', 'delete'
    timestamp: datetime

@greynet_fact
@dataclass()
class NetworkConnection:
    user: str
    dest_ip: str
    dest_port: int
    timestamp: datetime

@greynet_fact
@dataclass()
class AdminUser:
    username: str

# A Union type for convenience when starting the stream
SystemEvent = Union[LoginAttempt, FileAccess, NetworkConnection]

def define_security_constraints(builder: ConstraintBuilder):
    """
    Defines the sequence detection constraint.
    
    Pattern:
    1. A failed login attempt.
    2. Within 5 mins, a successful login for the SAME user from a DIFFERENT IP.
    3. Within 10 mins of success, the user accesses a sensitive file in /etc/.
    4. Within 2 mins of file access, the user makes an outbound connection on a known suspicious port (6667).
    5. The rule only triggers if the user is NOT a registered administrator.
    """

    # Helper predicate to validate the logic of the detected sequence
    def validate_complex_sequence(sequence: list[SystemEvent]) -> bool:
        # sequence[0] = Failed Login
        # sequence[1] = Successful Login
        # sequence[2] = File Access
        # sequence[3] = Network Connection
        
        failed_login, successful_login, file_access, network_conn = sequence

        # Condition 1: Same user throughout the sequence
        user = failed_login.user
        if not (user == successful_login.user == file_access.user == network_conn.user):
            return False

        # Condition 2: Successful login from a different IP
        if failed_login.ip_address == successful_login.ip_address:
            return False

        # Condition 3: Check intra-sequence time gaps
        if not (successful_login.timestamp - failed_login.timestamp <= timedelta(minutes=5)):
            return False
        if not (file_access.timestamp - successful_login.timestamp <= timedelta(minutes=10)):
            return False
        if not (network_conn.timestamp - file_access.timestamp <= timedelta(minutes=2)):
            return False
            
        return True

    @builder.constraint("anomalous_access_and_exfiltration", default_weight=1.0)
    def detect_attack_pattern():
        
        # The sequence of event types we are looking for
        pattern_steps = [
            lambda e: isinstance(e, LoginAttempt) and not e.successful,
            lambda e: isinstance(e, LoginAttempt) and e.successful,
            lambda e: isinstance(e, FileAccess) and e.file_path.startswith('/etc/'),
            lambda e: isinstance(e, NetworkConnection) and e.dest_port == 6667,
        ]

        return (
            builder.for_each(SystemEvent)
            # --- Start of Bug Fix ---
            .sequence(
                lambda e: e.timestamp,      # time_extractor is the first argument
                *pattern_steps,             # Unpack steps as positional arguments
                within=timedelta(minutes=15)# The entire sequence must complete within 15 mins
            )
            # --- End of Bug Fix ---
            # The stream now contains UniTuples where fact_a is a list of the 4 events
            .filter(lambda seq: validate_complex_sequence(seq))
            
            # Transform the stream of [event_list] into a stream of [username]
            .flat_map(lambda seq: [seq[0].user])
            
            # Now, check if this user exists in the AdminUser fact source.
            # Only propagate the username if they DO NOT exist in the admin list.
            .if_not_exists(
                AdminUser,
                left_key=lambda user_fact: user_fact, # The username from flat_map
                right_key=lambda admin_fact: admin_fact.username
            )
            # The stream now contains only usernames of non-admins who triggered the pattern.
            .penalize_hard(lambda user: 100) # Assign a penalty of 100 for each detected user.
        )

def run_simulation():
    # --- 1. Setup ---
    builder = ConstraintBuilder(name="SecurityRules", score_class=HardSoftScore)
    define_security_constraints(builder)
    session = builder.build()
    
    # --- 2. Test Data ---
    base_time = datetime(2025, 7, 15, 12, 0, 0)

    # Scenario 1: Malicious user 'intruder'
    # This sequence should trigger the rule.
    attack_sequence = [
        LoginAttempt(user='intruder', ip_address='1.1.1.1', timestamp=base_time, successful=False),
        LoginAttempt(user='intruder', ip_address='2.2.2.2', timestamp=base_time + timedelta(minutes=1), successful=True),
        FileAccess(user='intruder', file_path='/etc/shadow', operation='read', timestamp=base_time + timedelta(minutes=3),),
        NetworkConnection(user='intruder', dest_ip='3.3.3.3', dest_port=6667, timestamp=base_time + timedelta(minutes=4)),
    ]

    # Scenario 2: Admin user 's_admin' performs similar actions
    # This should NOT trigger the rule due to the 'if_not_exists' check.
    admin_actions = [
        LoginAttempt(user='s_admin', ip_address='10.0.0.1', timestamp=base_time + timedelta(hours=1), successful=False),
        LoginAttempt(user='s_admin', ip_address='10.0.0.2', timestamp=base_time + timedelta(hours=1, minutes=1), successful=True),
        FileAccess(user='s_admin', file_path='/etc/hosts', operation='write', timestamp=base_time + timedelta(hours=1, minutes=2)),
        NetworkConnection(user='s_admin', dest_ip='8.8.8.8', dest_port=6667, timestamp=base_time + timedelta(hours=1, minutes=3)),
    ]

    # --- 3. Execution ---
    session.insert_batch([AdminUser(username='s_admin')]) # Add the admin to the session
    session.insert_batch(attack_sequence)
    session.insert_batch(admin_actions)
    
    score = session.get_score()
    matches = session.get_constraint_matches()

    # --- 4. Display Results ---
    print("## Simulation Results\n")
    print(f"**Final Score:** {score}\n")
    
    if "anomalous_access_and_exfiltration" in matches:
        print("**Detected Violations for 'anomalous_access_and_exfiltration':**\n")
        
        for score_obj, tuple_obj in matches["anomalous_access_and_exfiltration"]:
            offending_user = tuple_obj.fact_a
            print(f"- **User:** `{offending_user}`")
            print(f"- **Penalty:** `{score_obj.simple_value}`")
            print("  - **Reason:** This user, who is not an administrator, performed a sequence of actions matching the attack pattern.")
    else:
        print("**No violations detected.**")


if __name__ == "__main__":
    run_simulation()
