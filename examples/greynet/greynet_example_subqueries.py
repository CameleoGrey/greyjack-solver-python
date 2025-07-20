# main_complex_example.py
from dataclasses import dataclass, field
from typing import Set

from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, JoinerType
from greyjack.score_calculation.scores.HardMediumSoftScore import HardMediumSoftScore

# --- Data Models ---

@greynet_fact
@dataclass()
class Client:
    client_id: str
    name: str
    status: str  # e.g., 'VIP', 'Standard'

@greynet_fact
@dataclass()
class Project:
    project_id: str
    client_id: str
    primary_skill: str # Simplified to one primary skill for clarity
    budget: float

@greynet_fact
@dataclass()
class Employee:
    employee_id: str
    name: str
    skills: Set[str]

@greynet_fact
@dataclass()
class Assignment:
    assignment_id: str
    project_id: str
    employee_id: str
    status: str # e.g., 'Active', 'Completed'

@greynet_fact
@dataclass()
class Invoice:
    invoice_id: str
    project_id: str
    amount: float

@greynet_fact
@dataclass()
class TrainingModule:
    module_id: str
    skill_taught: str
    
@greynet_fact
@dataclass()
class TrainingCompletion:
    employee_id: str
    module_id: str

# --- Constraint Definitions ---
builder = ConstraintBuilder(name="talent-management", score_class=HardMediumSoftScore)

# ---
# Rule 1: Missing Invoice for VIP Client Project
# ---
@builder.constraint("Missing Invoice for VIP Project")
def missing_invoice_for_vip_project():
    active_assignments = builder.for_each(Assignment).filter(lambda a: a.status == 'Active')
    
    vip_projects = (
        active_assignments.join(
            builder.for_each(Project),
            JoinerType.EQUAL,
            left_key_func=lambda a: a.project_id,
            right_key_func=lambda p: p.project_id
        ).join(
            builder.for_each(Client),
            JoinerType.EQUAL,
            left_key_func=lambda a, p: p.client_id,
            right_key_func=lambda c: c.client_id
        ).filter(lambda a, p, c: c.status == 'VIP')
    )
    
    return (
        vip_projects.if_not_exists(
            Invoice,
            left_key=lambda a, p, c: p.project_id,
            right_key=lambda inv: inv.project_id
        ).penalize_medium(250)
    )

# ---
# Rule 2: Training Dead-End Assignment
# ---
@builder.constraint("Training Dead-End Assignment")
def training_dead_end():
    assignments = builder.for_each(Assignment).join(
        builder.for_each(Employee),
        JoinerType.EQUAL,
        lambda a: a.employee_id,
        lambda e: e.employee_id
    ).join(
        builder.for_each(Project),
        JoinerType.EQUAL,
        lambda a, e: a.project_id,
        lambda p: p.project_id
    )
    
    # Logic Fix: Added filter for 'Active' status to avoid flagging completed projects.
    mismatched_assignments = assignments.filter(
        lambda a, e, p: a.status == 'Active' and p.primary_skill not in e.skills
    )
    
    return (
        mismatched_assignments.if_not_exists(
            TrainingModule,
            left_key=lambda a, e, p: p.primary_skill,
            right_key=lambda tm: tm.skill_taught
        ).penalize_hard(1000)
    )

# ---
# Rule 3: Bonus for Trained Employee on VIP Project Completion
# ---
@builder.constraint("Bonus Flag: VIP Project Completion by Trained Employee")
def bonus_for_vip_completion():
    completed_vip_assignments = (
        builder.for_each(Assignment)
            .filter(lambda a: a.status == 'Completed')
            .join(builder.for_each(Project), JoinerType.EQUAL, lambda a: a.project_id, lambda p: p.project_id)
            .join(builder.for_each(Client), JoinerType.EQUAL, lambda a, p: p.client_id, lambda c: c.client_id)
            .filter(lambda a, p, c: c.status == 'VIP')
    )
    
    return (
        completed_vip_assignments.if_exists(
            TrainingCompletion,
            left_key=lambda a, p, c: (a.employee_id, 'CR-101'),
            right_key=lambda tc: (tc.employee_id, tc.module_id)
        ).penalize_soft(1)
    )

# --- Execution and Verification ---
print("--- Building the session ---")
session = builder.build()

# --- Initial Data Setup ---
client_vip = Client("C01", "GlobalTech Inc.", "VIP")
client_std = Client("C02", "Local Motors", "Standard")
emp_ana = Employee("E01", "Ana", skills={"Python", "SQL"})
emp_ben = Employee("E02", "Ben", skills={"Java"})
emp_carl = Employee("E03", "Carl", skills={"SQL"})
proj_ai = Project("P01", "C01", "AI/ML", 100_000)
proj_java = Project("P02", "C02", "Java", 50_000)
proj_cloud = Project("P03", "C01", "CloudInfra", 75_000)
train_python = TrainingModule("TM-01", "Python")
train_relations = TrainingModule("CR-101", "Customer Relations")
ana_training_completion = TrainingCompletion("E01", "CR-101")
assign_ana_ai = Assignment("A01", "P01", "E01", "Active")
assign_ben_java = Assignment("A02", "P02", "E02", "Active")
assign_carl_cloud = Assignment("A03", "P03", "E03", "Active")

initial_facts = [
    client_vip, client_std,
    emp_ana, emp_ben, emp_carl,
    proj_ai, proj_java, proj_cloud,
    train_python, train_relations, ana_training_completion,
    assign_ana_ai, assign_ben_java, assign_carl_cloud
]

def print_violations():
    matches = session.get_constraint_matches()
    print(f"\nScore: {session.get_score()} (Hard|Medium|Soft)")
    if not matches:
        print("  No violations found.")
        return
    for constraint_id, violations in matches.items():
        print(f"  - Violation: '{constraint_id}'")
        for score, facts in violations:
            # Display only the first fact for brevity in complex joins
            fact_display = getattr(facts, 'fact_a', facts)
            print(f"    - Details: {fact_display}, Score Impact: {score}")

# --- 1. Initial State ---
print("\n--- 1. Evaluating Initial State ---")
session.insert_batch(initial_facts)
print_violations()

# --- 2. Resolving Violations ---
print("\n\n--- 2. Resolving Violations by Adding Facts ---")
invoice_for_ai = Invoice("INV-001", "P01", 100_000)
print(f"\nAction: Inserting invoice for project {invoice_for_ai.project_id}...")
session.insert(invoice_for_ai)
print_violations()

train_cloud = TrainingModule("TM-03", "CloudInfra")
print(f"\nAction: Adding training module for skill '{train_cloud.skill_taught}'...")
session.insert(train_cloud)
print_violations()

# --- 3. Triggering a New 'Bonus' Flag ---
print("\n\n--- 3. Triggering a Bonus by Completing a Project ---")
completed_assign_ana_ai = Assignment("A01", "P01", "E01", "Completed")
print("\nAction: Ana completes the VIP AI project...")
session.retract(assign_ana_ai)
session.insert(completed_assign_ana_ai)
print_violations()

# --- 4. Final State ---
print("\n\n--- 4. Final State ---")
print("The system has dynamically adapted to changes, resolving hard/medium violations")
print("and flagging a new soft-priority item (the bonus).")
