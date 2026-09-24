"""
Demo data generator from Timefold repo (with a little changes)

                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""


# Modified for the standalone OR-Tools example: immutable parameter values,
# per-call generation state, explicit dates, honored caller seeds, and integer IDs.
# The Timefold-derived generator's random calls and their order are preserved.

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from itertools import count, product
from random import Random
from typing import Iterator

from ..domain import Employee, EmployeeSchedule, Shift


class DemoData(Enum):
    SMALL = "SMALL"
    LARGE = "LARGE"


@dataclass(frozen=True, kw_only=True)
class CountDistribution:
    count: int
    weight: float


def counts(distributions: tuple[CountDistribution, ...]) -> tuple[int, ...]:
    return tuple(distribution.count for distribution in distributions)


def weights(distributions: tuple[CountDistribution, ...]) -> tuple[float, ...]:
    return tuple(distribution.weight for distribution in distributions)


@dataclass(frozen=True, kw_only=True)
class DemoDataParameters:
    locations: tuple[str, ...]
    required_skills: tuple[str, ...]
    optional_skills: tuple[str, ...]
    days_in_schedule: int
    employee_count: int
    optional_skill_distribution: tuple[CountDistribution, ...]
    shift_count_distribution: tuple[CountDistribution, ...]
    availability_count_distribution: tuple[CountDistribution, ...]
    random_seed: int = 37


def parameters_for(dataset: DemoData, random_seed: int = 37) -> DemoDataParameters:
    """Return fresh immutable parameters instead of mutating a global dataset map."""
    if dataset not in (DemoData.SMALL, DemoData.LARGE):
        raise ValueError("Unknown demo dataset")
    small = dataset is DemoData.SMALL
    return DemoDataParameters(
        locations=("Ambulatory care", "Critical care", "Pediatric care")
        if small
        else (
            "Ambulatory care",
            "Neurology",
            "Critical care",
            "Pediatric care",
            "Surgery",
            "Radiology",
            "Outpatient",
        ),
        required_skills=("Doctor", "Nurse"),
        optional_skills=("Anaesthetics", "Cardiology")
        if small
        else ("Anaesthetics", "Cardiology", "Radiology"),
        days_in_schedule=14 if small else 28,
        employee_count=15 if small else 50,
        optional_skill_distribution=(
            CountDistribution(count=1, weight=3),
            CountDistribution(count=2, weight=1),
        ),
        shift_count_distribution=(
            CountDistribution(count=1, weight=0.9),
            CountDistribution(count=2, weight=0.1),
        )
        if small
        else (
            CountDistribution(count=1, weight=0.5),
            CountDistribution(count=2, weight=0.3),
            CountDistribution(count=3, weight=0.2),
        ),
        availability_count_distribution=(
            CountDistribution(count=1, weight=4),
            CountDistribution(count=2, weight=3),
            CountDistribution(count=3, weight=2),
            CountDistribution(count=4, weight=1),
        )
        if small
        else (
            CountDistribution(count=5, weight=4),
            CountDistribution(count=10, weight=3),
            CountDistribution(count=15, weight=2),
            CountDistribution(count=20, weight=1),
        ),
        random_seed=random_seed,
    )


FIRST_NAMES = ("Amy", "Beth", "Carl", "Dan", "Elsa", "Flo", "Gus", "Hugo", "Ivy", "Jay")
LAST_NAMES = (
    "Cole",
    "Fox",
    "Green",
    "Jones",
    "King",
    "Li",
    "Poe",
    "Rye",
    "Smith",
    "Watt",
)
SHIFT_LENGTH = timedelta(hours=8)
MORNING_SHIFT_START_TIME = time(hour=6, minute=0)
DAY_SHIFT_START_TIME = time(hour=9, minute=0)
AFTERNOON_SHIFT_START_TIME = time(hour=14, minute=0)
NIGHT_SHIFT_START_TIME = time(hour=22, minute=0)
SHIFT_START_TIMES_COMBOS = (
    (MORNING_SHIFT_START_TIME, AFTERNOON_SHIFT_START_TIME),
    (MORNING_SHIFT_START_TIME, AFTERNOON_SHIFT_START_TIME, NIGHT_SHIFT_START_TIME),
    (
        MORNING_SHIFT_START_TIME,
        DAY_SHIFT_START_TIME,
        AFTERNOON_SHIFT_START_TIME,
        NIGHT_SHIFT_START_TIME,
    ),
)


def earliest_monday_on_or_after(target_date: date) -> date:
    """Return the same date if Monday, otherwise the following Monday."""
    return target_date + timedelta(days=(7 - target_date.weekday()) % 7)


def generate_demo_data(
    demo_data_or_parameters: DemoData | DemoDataParameters,
    *,
    start_date: date | None = None,
) -> EmployeeSchedule:
    parameters = (
        parameters_for(demo_data_or_parameters)
        if isinstance(demo_data_or_parameters, DemoData)
        else demo_data_or_parameters
    )
    if start_date is None:
        start_date = earliest_monday_on_or_after(date.today())
    if not isinstance(start_date, date) or isinstance(start_date, datetime):
        raise ValueError("start_date must be a date-only value")
    random = Random(parameters.random_seed)
    name_permutations = [
        f"{first_name} {last_name}"
        for first_name, last_name in product(FIRST_NAMES, LAST_NAMES)
    ]
    random.shuffle(name_permutations)

    employees = []
    for i in range(parameters.employee_count):
        (skill_count,) = random.choices(
            population=counts(parameters.optional_skill_distribution),
            weights=weights(parameters.optional_skill_distribution),
        )
        skills = []
        skills += random.sample(parameters.optional_skills, skill_count)
        skills += random.sample(parameters.required_skills, 1)
        employees.append(Employee(name=name_permutations[i], skills=skills))

    shifts: list[Shift] = []
    ids = count()
    for i in range(parameters.days_in_schedule):
        (availability_count,) = random.choices(
            population=counts(parameters.availability_count_distribution),
            weights=weights(parameters.availability_count_distribution),
        )
        employees_with_availabilities_on_day = random.sample(
            employees, availability_count
        )
        current_date = start_date + timedelta(days=i)
        for employee in employees_with_availabilities_on_day:
            rand_num = random.randint(0, 2)
            if rand_num == 0:
                employee.unavailable_dates.append(current_date)
            elif rand_num == 1:
                employee.undesired_dates.append(current_date)
            elif rand_num == 2:
                employee.desired_dates.append(current_date)
        shifts += generate_shifts_for_day(parameters, current_date, random, ids)
    return EmployeeSchedule(employees=employees, shifts=shifts)


def generate_shifts_for_day(
    parameters: DemoDataParameters,
    current_date: date,
    random: Random,
    ids: Iterator[int],
) -> list[Shift]:
    shifts = []
    for index, location in enumerate(parameters.locations):
        shift_start_times = SHIFT_START_TIMES_COMBOS[
            index % len(SHIFT_START_TIMES_COMBOS)
        ]
        for start_time in shift_start_times:
            shift_start_date_time = datetime.combine(current_date, start_time)
            shift_end_date_time = shift_start_date_time + SHIFT_LENGTH
            shifts += generate_shifts_for_timeslot(
                parameters,
                shift_start_date_time,
                shift_end_date_time,
                location,
                random,
                ids,
            )
    return shifts


def generate_shifts_for_timeslot(
    parameters: DemoDataParameters,
    timeslot_start: datetime,
    timeslot_end: datetime,
    location: str,
    random: Random,
    ids: Iterator[int],
) -> list[Shift]:
    (shift_count,) = random.choices(
        population=counts(parameters.shift_count_distribution),
        weights=weights(parameters.shift_count_distribution),
    )
    shifts = []
    for _ in range(shift_count):
        if random.random() >= 0.5:
            required_skill = random.choice(parameters.required_skills)
        else:
            required_skill = random.choice(parameters.optional_skills)
        shifts.append(
            Shift(
                id=next(ids),
                start=timeslot_start,
                end=timeslot_end,
                location=location,
                required_skill=required_skill,
            )
        )
    return shifts
