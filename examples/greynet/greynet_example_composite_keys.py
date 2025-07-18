from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Any
from datetime import datetime, timedelta

# Assume the framework classes from your project are available
from greyjack.score_calculation.greynet.greynet_fact import *
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors
from greyjack.score_calculation.greynet.common.joiner_type import JoinerType
from greyjack.score_calculation.scores.SimpleScore import SimpleScore
from greyjack.score_calculation.greynet.session import Session

# --- Example Fact Definitions ---
@greynet_fact
@dataclass()
class Doctor:
    id: str
    name: str
    specialty: str  # e.g., 'Cardiology', 'Surgery', 'Psychiatry'

@greynet_fact
@dataclass()
class Room:
    id: str
    type: str  # e.g., 'Operating Room', 'ICU', 'Consultation', 'Psych Ward'
    capacity: int

@greynet_fact
@dataclass()
class ProcedureInfo:
    code: str
    description: str
    required_specialty: str
    required_room_type: str

@greynet_fact
@dataclass()
class Appointment:
    id: str
    patient_name: str
    doctor_id: str
    room_id: str
    procedure_code: str
    patient_acuity: int  # Scale 1-5 (5 is highest acuity)
    start_time: datetime
    end_time: datetime = field(init=False)

    def __post_init__(self):
        # Appointments are 1 hour long for simplicity
        object.__setattr__(self, 'end_time', self.start_time + timedelta(hours=1))

# --- CONSTRAINT DEFINITIONS ---

builder = ConstraintBuilder(name="hospital_schedule_validator", score_class=SimpleScore)


@builder.constraint("room_double_booking")
def room_double_booking():
    """
    Finds cases where two different appointments are scheduled in the same room
    at the exact same time. This is a classic composite key equality join.
    The composite key is (room_id, start_time).
    """
    appointments = builder.for_each(Appointment)
    return (
        appointments.join(
            appointments,
            joiner_type=JoinerType.EQUAL,
            # The composite key is a tuple of the fields we want to match on.
            left_key_func=lambda app: (app.room_id, app.start_time),
            right_key_func=lambda app: (app.room_id, app.start_time)
        )
        # Filter to avoid matching an appointment with itself and to report each pair only once.
        .filter(lambda app1, app2: app1.id < app2.id)
        .penalize_simple(25)  # High penalty for a critical error
    )


@builder.constraint("resource_allocation_mismatch")
def resource_allocation_mismatch():
    """
    Finds appointments where the doctor or room is misaligned with procedure requirements.
    This demonstrates a multi-stage join process, followed by filtering.
    """
    # Create streams for all our base facts
    appointments = builder.for_each(Appointment)
    doctors = builder.for_each(Doctor)
    rooms = builder.for_each(Room)
    procedures = builder.for_each(ProcedureInfo)

    # Stage 1: Join Appointments with Doctors
    app_with_doc = appointments.join(
        doctors, JoinerType.EQUAL,
        left_key_func=lambda app: app.doctor_id,
        right_key_func=lambda doc: doc.id
    )

    # Stage 2: Join the result with Rooms
    app_with_doc_room = app_with_doc.join(
        rooms, JoinerType.EQUAL,
        left_key_func=lambda app, doc: app.room_id,
        right_key_func=lambda room: room.id
    )

    # Stage 3: Join with ProcedureInfo to get the requirements for each appointment.
    # This is a standard join on a primary key (the procedure code). The filtering
    # for mismatches happens in the subsequent .filter() step.
    final_join = app_with_doc_room.join(
        procedures, JoinerType.EQUAL,
        left_key_func=lambda app, doc, room: app.procedure_code,
        right_key_func=lambda proc: proc.code
    )

    return (
        final_join
        .filter(
            lambda app, doc, room, proc: (
                doc.specialty != proc.required_specialty or
                room.type != proc.required_room_type
            )
        )
        .penalize_simple(10)  # Heavy penalty for resource mismatch
    )


@builder.constraint("scheduling_priority_inversion")
def scheduling_priority_inversion():
    """
    Finds cases where a doctor handles a low-priority case before a high-priority
    case on the same day. This is achieved by first grouping appointments by
    doctor and day, and then filtering for priority/time inversions.
    """
    appointments = builder.for_each(Appointment)

    # Define the composite key for grouping: (doctor_id, date)
    def get_grouping_key(app: Appointment) -> tuple:
        return (app.doctor_id, app.start_time.date())

    return (
        appointments.join(
            appointments,
            joiner_type=JoinerType.EQUAL,
            left_key_func=get_grouping_key,
            right_key_func=get_grouping_key
        )
        # Filter 1: Ensure we only consider each unique pair of appointments once.
        # This prevents finding both (A, B) and (B, A) as separate issues.
        .filter(
            lambda app1, app2: app1.id < app2.id
        )
        # Filter 2: The actual inversion logic.
        # An inversion exists if the appointment with the higher acuity is scheduled
        # LATER than the one with the lower acuity.
        .filter(
            lambda app1, app2: (
                (app1.patient_acuity > app2.patient_acuity and app1.start_time > app2.start_time) or
                (app2.patient_acuity > app1.patient_acuity and app2.start_time > app1.start_time)
            )
        )
        .penalize_simple(5)
    )



# --- DATA POPULATION & SIMULATION EXECUTION ---

def populate_data() -> List[Any]:
    """Creates a set of carefully crafted facts to trigger our constraints."""

    # --- Resources ---
    doc_surgeon = Doctor(id="D1", name="Dr. Anya Sharma", specialty="Surgery")
    doc_cardiologist = Doctor(id="D2", name="Dr. Ben Carter", specialty="Cardiology")
    doc_psychiatrist = Doctor(id="D3", name="Dr. Chloe Davis", specialty="Psychiatry")

    room_or = Room(id="R1", type="Operating Room", capacity=1)
    room_consult = Room(id="R2", type="Consultation", capacity=1)
    room_psych = Room(id="R3", type="Psych Ward", capacity=1)

    proc_bypass = ProcedureInfo(code="PROC-001", description="Heart Bypass", required_specialty="Surgery", required_room_type="Operating Room")
    proc_eval = ProcedureInfo(code="PROC-002", description="Cardiac Evaluation", required_specialty="Cardiology", required_room_type="Consultation")
    proc_therapy = ProcedureInfo(code="PROC-003", description="Cognitive Therapy", required_specialty="Psychiatry", required_room_type="Psych Ward")

    # --- Schedule for a single day ---
    today = datetime.now().date()

    appointments = [
        # --- Correctly Scheduled Appointments ---
        Appointment(id="A1", patient_name="John Smith", doctor_id="D2", room_id="R2", procedure_code="PROC-002", patient_acuity=3, start_time=datetime.combine(today, datetime.min.time(),).replace(hour=9)),
        Appointment(id="A2", patient_name="Jane Doe", doctor_id="D1", room_id="R1", procedure_code="PROC-001", patient_acuity=5, start_time=datetime.combine(today, datetime.min.time(),).replace(hour=11)),

        # --- CONSTRAINT 1 (Resource Mismatch) TRIGGERS ---
        Appointment(id="A3", patient_name="Peter Jones", doctor_id="D1", room_id="R2", procedure_code="PROC-001", patient_acuity=4, start_time=datetime.combine(today, datetime.min.time(),).replace(hour=14)),
        Appointment(id="A4", patient_name="Mary Williams", doctor_id="D3", room_id="R2", procedure_code="PROC-002", patient_acuity=2, start_time=datetime.combine(today, datetime.min.time(),).replace(hour=10)),

        # --- CONSTRAINT 2 (Priority Inversion) TRIGGERS ---
        Appointment(id="A5", patient_name="Kevin Brown", doctor_id="D2", room_id="R2", procedure_code="PROC-002", patient_acuity=2, start_time=datetime.combine(today, datetime.min.time(),).replace(hour=13)),
        Appointment(id="A6", patient_name="Laura Green", doctor_id="D2", room_id="R2", procedure_code="PROC-002", patient_acuity=5, start_time=datetime.combine(today, datetime.min.time(),).replace(hour=15)),

        # --- CONSTRAINT 3 (Double Booking) TRIGGER ---
        # Appointment A7 is scheduled in the same room (R2) at the same time as A1.
        Appointment(id="A7", patient_name="Susan King", doctor_id="D3", room_id="R2", procedure_code="PROC-003", patient_acuity=1, start_time=datetime.combine(today, datetime.min.time(),).replace(hour=9)),
    ]

    return [doc_surgeon, doc_cardiologist, doc_psychiatrist, room_or, room_consult, room_psych, proc_bypass, proc_eval, proc_therapy] + appointments


if __name__ == "__main__":

    print("=" * 80)
    print("RUNNING HOSPITAL SCHEDULING VALIDATOR")
    print("=" * 80)

    # 1. Build the session from our constraint definitions
    session = builder.build()

    # 2. Populate the session with facts
    all_facts = populate_data()
    session.insert_batch(all_facts)
    print(f"INFO: Inserted {len(all_facts)} facts into the session.")

    # 3. Fire the rules
    print("INFO: Firing all rules and evaluating constraints...")
    session.flush()
    print("\n")

    # 4. Analyze and report the results
    print("=" * 80)
    print("VALIDATION REPORT")
    print("=" * 80)

    matches = session.get_constraint_matches()

    if not matches:
        print("SUCCESS: No constraint violations found. The schedule is valid.")
    else:
        # --- Report on Double Bookings ---
        if "room_double_booking" in matches:
            print("\n--- VIOLATION: Room Double Booking (Penalty: 25 per issue) ---")
            for i, (score, match_facts) in enumerate(matches["room_double_booking"]):
                
                # Unpack facts from the BiTuple object's attributes
                app1, app2 = match_facts.fact_a, match_facts.fact_b
                
                print(f"\n  Issue #{i+1}: Room '{app1.room_id}' is double-booked at {app1.start_time.strftime('%I:%M %p')}.")
                print(f"    - Appointment ID: {app1.id} (Patient: {app1.patient_name})")
                print(f"    - Appointment ID: {app2.id} (Patient: {app2.patient_name})")

        # --- Report on Resource Mismatches ---
        if "resource_allocation_mismatch" in matches:
            print("\n--- VIOLATION: Resource Allocation Mismatch (Penalty: 10 per issue) ---")
            for i, (score, match_facts) in enumerate(matches["resource_allocation_mismatch"]):
                
                # This join chain results in a QuadTuple
                app, doc, room, proc = match_facts.fact_a, match_facts.fact_b, match_facts.fact_c, match_facts.fact_d
                
                print(f"\n  Issue #{i+1}: Appointment '{app.id}' for patient '{app.patient_name}'")
                print(f"    Procedure: '{proc.description}' ({proc.code})")
                if doc.specialty != proc.required_specialty:
                    print(f"    [X] Specialty Mismatch: Doctor '{doc.name}' is a '{doc.specialty}', but procedure requires a '{proc.required_specialty}'.")
                if room.type != proc.required_room_type:
                    print(f"    [X] Room Mismatch: Room '{room.id}' is a '{room.type}', but procedure requires a '{proc.required_room_type}'.")

        # --- Report on Priority Inversions ---
        if "scheduling_priority_inversion" in matches:
            print("\n--- VIOLATION: Scheduling Priority Inversion (Penalty: 5 per issue) ---")
            for i, (score, match_facts) in enumerate(matches["scheduling_priority_inversion"]):
                
                # This self-join results in a BiTuple
                high_app, low_app = match_facts.fact_a, match_facts.fact_b
                
                doctor_name = next((d.name for d in all_facts if isinstance(d, Doctor) and d.id == high_app.doctor_id), "Unknown")
                print(f"\n  Issue #{i+1}: Inefficient scheduling for Dr. {doctor_name}")
                print(f"    - High Acuity Patient '{high_app.patient_name}' (Acuity: {high_app.patient_acuity}) is scheduled at {high_app.start_time.strftime('%I:%M %p')}.")
                print(f"    - Low Acuity Patient '{low_app.patient_name}' (Acuity: {low_app.patient_acuity}) is scheduled EARLIER at {low_app.start_time.strftime('%I:%M %p')}.")
                print("    [!] Recommendation: Prioritize high-acuity patients by scheduling them earlier in the day.")
        
                # --- Report on Priority Inversions ---
        if "scheduling_priority_inversion" in matches:
            print("\n--- VIOLATION: Scheduling Priority Inversion (Penalty: 5 per issue) ---")
            for i, (score, match_facts) in enumerate(matches["scheduling_priority_inversion"]):
                
                # Unpack the generic pair from the BiTuple
                app1, app2 = match_facts.fact_a, match_facts.fact_b

                # Dynamically determine which is the high-acuity and low-acuity appointment
                if app1.patient_acuity > app2.patient_acuity:
                    high_app, low_app = app1, app2
                else:
                    high_app, low_app = app2, app1
                

                doctor_name = next((d.name for d in all_facts if isinstance(d, Doctor) and d.id == high_app.doctor_id), "Unknown")
                print(f"\n  Issue #{i+1}: Inefficient scheduling for Dr. {doctor_name}")
                print(f"    - High Acuity Patient '{high_app.patient_name}' (Acuity: {high_app.patient_acuity}) is scheduled at {high_app.start_time.strftime('%I:%M %p')}.")
                print(f"    - Low Acuity Patient '{low_app.patient_name}' (Acuity: {low_app.patient_acuity}) is scheduled EARLIER at {low_app.start_time.strftime('%I:%M %p')}.")
                print("    [!] Recommendation: Prioritize high-acuity patients by scheduling them earlier in the day.")


    # 5. Print the final score
    total_score = session.get_score()
    print("\n" + "=" * 80)
    print(f"FINAL SCHEDULING PENALTY SCORE: {total_score.simple_value}")
    print("A lower score indicates a better, more valid schedule.")
    print("=" * 80)

