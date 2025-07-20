from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Set


# Import the new builder and the desired score class.
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, JoinerType, Collectors
from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore


# --- 1. Data Models ---
# Define the "facts" that will drive the rule engine.

@greynet_fact
@dataclass()
class Employee:
    name: str
    skills: Set[str] = field(default_factory=set)
    unavailable_dates: Set[date] = field(default_factory=set)

@greynet_fact
@dataclass()
class Shift:
    shift_id: str
    employee_name: str
    shift_date: date
    start_time: int
    end_time: int
    required_skill: str

    @property
    def duration(self) -> int:
        return self.end_time - self.start_time

@greynet_fact
@dataclass()
class CompanyPolicy:
    max_consecutive_work_days: int = 6

# --- 2. Constraint Definitions ---
# Initialize the builder with the chosen score class.
builder = ConstraintBuilder(name="advanced-scheduling", score_class=HardMediumSoftScore)

# --- Rule 1: Skill Match (Medium Priority) ---
@builder.constraint("Required skill missing")
def required_skill_missing():
    return (
        builder.for_each(Shift)
            .join(
                builder.for_each(Employee),
                JoinerType.EQUAL,
                left_key_func=lambda shift: shift.employee_name,
                right_key_func=lambda employee: employee.name
            )
            .filter(lambda shift, employee: shift.required_skill not in employee.skills)
            .penalize_medium(1.0) # Use new penalty method
    )

# --- Rule 2: Employee Existence (Hard Priority) ---
@builder.constraint("Shift for non-existent employee")
def shift_for_non_existent_employee():
    return (
        builder.for_each(Shift)
            .if_not_exists(
                Employee,
                # FIX: Removed JoinerType.EQUAL, which was an invalid argument.
                left_key=lambda shift: shift.employee_name,
                right_key=lambda employee: employee.name
            )
            .penalize_hard(1.0) # Use new penalty method
    )

# --- Rule 3: Availability (Medium Priority) ---
@builder.constraint("Scheduled on unavailable day")
def scheduled_on_unavailable_day():
    return (
        builder.for_each(Shift)
            .join(
                builder.for_each(Employee),
                JoinerType.EQUAL,
                left_key_func=lambda shift: shift.employee_name,
                right_key_func=lambda employee: employee.name
            )
            .filter(lambda shift, employee: shift.shift_date in employee.unavailable_dates)
            .penalize_medium(1.0) # Use new penalty method
    )

# --- Rule 4: Overlapping Shifts (Hard Priority) ---
@builder.constraint("Overlapping shifts")
def overlapping_shifts():
    return (
        builder.for_each(Shift)
            .join(
                builder.for_each(Shift),
                JoinerType.EQUAL,
                left_key_func=lambda s: (s.employee_name, s.shift_date),
                right_key_func=lambda s: (s.employee_name, s.shift_date)
            )
            .filter(lambda s1, s2: id(s1) < id(s2))
            .filter(lambda s1, s2: max(s1.start_time, s2.start_time) < min(s1.end_time, s2.end_time))
            .penalize_hard(1.0) # Use new penalty method
    )


# --- 3. Execution and Verification (Updated for new score object) ---

print("--- Building Greynet Session ---")
session = builder.build()

employee_ana = Employee("Ana", skills={"Cashier", "Manager"}, unavailable_dates={date(2025, 7, 18)})
employee_ben = Employee("Ben", skills={"Chef"})
policy = CompanyPolicy(max_consecutive_work_days=5)

shifts = [
    Shift("S01", "Ben", date(2025, 7, 14), 9, 17, "Chef"), Shift("S02", "Ben", date(2025, 7, 15), 9, 17, "Chef"),
    Shift("S03", "Ben", date(2025, 7, 16), 9, 17, "Chef"), Shift("S04", "Ben", date(2025, 7, 17), 9, 17, "Chef"),
    Shift("S05", "Ben", date(2025, 7, 18), 9, 17, "Chef"), Shift("S06", "Ben", date(2025, 7, 19), 9, 17, "Chef"),
    Shift("S07", "Ana", date(2025, 7, 15), 9, 18, "Cashier"), Shift("S08", "Ana", date(2025, 7, 15), 17, 20, "Manager"),
    Shift("S09", "Ana", date(2025, 7, 16), 9, 17, "Chef"), Shift("S10", "Ana", date(2025, 7, 18), 10, 16, "Cashier"),
    Shift("S11", "Charlie", date(2025, 7, 14), 9, 17, "Cashier")
]

print(f"\nInitial Score: {session.get_score()} (Hard|Medium|Soft)")

print("\n--- Inserting all facts into the session ---")
session.insert_batch([employee_ana, employee_ben, policy] + shifts)
session.flush()

print(f"\nScore after insert: {session.get_score()} (Hard|Medium|Soft)")

print("\nConstraint Violations:")
matches = session.get_constraint_matches()
for constraint_id, violations in matches.items():
    # Use get_sum_abs() to show the total magnitude of the penalty.
    total_penalty = sum(s.get_sum_abs() for s, _ in violations)
    print(f"  - {constraint_id} (Total Penalty: {total_penalty})")
    for score, facts_tuple in violations:
        facts_list = [f for f in (getattr(facts_tuple, attr, None) for attr in ['fact_a', 'fact_b', 'fact_c', 'fact_d', 'fact_e']) if f is not None]
        print(f"    - Violation with facts: {facts_list}, Score Impact: {score}")

session.update_constraint_weight("Scheduled on unavailable day", 10.0)
session.update_constraint_weight("Overlapping shifts", 20.0)

print(f"\nScore after updating constraint weights: {session.get_score()} (Hard|Medium|Soft)")

print("\nConstraint Violations after updating constraint weights:")
matches = session.get_constraint_matches()
for constraint_id, violations in matches.items():
    # Use get_sum_abs() to show the total magnitude of the penalty.
    total_penalty = sum(s.get_sum_abs() for s, _ in violations)
    print(f"  - {constraint_id} (Total Penalty: {total_penalty})")
    for score, facts_tuple in violations:
        facts_list = [f for f in (getattr(facts_tuple, attr, None) for attr in ['fact_a', 'fact_b', 'fact_c', 'fact_d', 'fact_e']) if f is not None]
        print(f"    - Violation with facts: {facts_list}, Score Impact: {score}")

print("\n--- Retracting Ana's overlapping shift (S08) ---")
session.retract(next(s for s in shifts if s.shift_id == "S08"))
session.flush()
print(f"Score after retracting S08: {session.get_score()} (Hard|Medium|Soft)")

print("\n--- Correcting Ana's skill-mismatch shift (S09) ---")
session.retract(next(s for s in shifts if s.shift_id == "S09"))
session.insert(Shift("S09-FIXED", "Ana", date(2025, 7, 16), 9, 17, "Manager"))
session.flush()
print(f"Score after correcting S09: {session.get_score()} (Hard|Medium|Soft)")

print("\n--- Final Violations ---")
matches = session.get_constraint_matches()
for constraint_id, violations in matches.items():
    print(f"  - {constraint_id}")
    for score, facts_tuple in violations:
        facts_list = [f for f in (getattr(facts_tuple, attr, None) for attr in ['fact_a', 'fact_b', 'fact_c', 'fact_d', 'fact_e']) if f is not None]
        print(f"    - Remaining violation with facts: {facts_list}")

print("\n--- Example Complete ---")
