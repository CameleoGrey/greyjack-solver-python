from datetime import datetime, time, timedelta
from random import Random
from typing import Dict, List, Set
from examples.object_oriented.food_packaging.domain import *

"""
Demo data generator from Timefold repo (with a little changes)
"""
"""
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

class DemoDataGenerator:
    INGREDIENT_LIST = [
        "Carrots",
        "Peas",
        "Cabbage",
        "Tomato",
        "Eggplant",
        "Broccoli",
        "Spinach",
        "Pumpkin",
        "Pepper",
        "Onions"
    ]
    
    PRODUCT_VARIATION_LIST = [
        "small bag",
        "medium bag",
        "large bag"
    ]

    def __init__(self, line_count=5, job_count=100):
        self.line_count = line_count
        self.job_count = job_count

    def generate_demo_data(self):
        no_cleaning_minutes = 10
        cleaning_minutes_minimum = 30
        cleaning_minutes_maximum = 60
        job_duration_minutes_minimum = 120
        job_duration_minutes_maximum = 300
        average_cleaning_and_job_duration_minutes = (
            (2 * no_cleaning_minutes + cleaning_minutes_minimum + cleaning_minutes_maximum) // 4
            + (job_duration_minutes_minimum + job_duration_minutes_maximum) // 2
        )

        today = datetime.now().date()
        start_date = self._next_weekday(today, 0)  # 0 is Monday
        start_date_time = datetime.combine(start_date, time.min)
        end_date = start_date + timedelta(weeks=2)
        end_date_time = datetime.combine(end_date, time.min)

        random = Random(37)
        solution = PackagingSchedule()

        ingredient_map = {}
        product_id = 0
        for i, ingredient in enumerate(self.INGREDIENT_LIST):
            r = random.randint(0, len(self.INGREDIENT_LIST) - 5)
            ingredient_a = self.INGREDIENT_LIST[(i + r + 1) % len(self.INGREDIENT_LIST)]
            ingredient_b = self.INGREDIENT_LIST[(i + r + 2) % len(self.INGREDIENT_LIST)]
            ingredient_c = self.INGREDIENT_LIST[(i + r + 3) % len(self.INGREDIENT_LIST)]
            
            for product_variation in self.PRODUCT_VARIATION_LIST:
                ingredient_map[Product(product_id, f"{ingredient} {product_variation}")] = {ingredient}
                product_id += 1
            
            ingredient_map[Product(product_id, f"{ingredient} and {ingredient_a} {self.PRODUCT_VARIATION_LIST[1]}")] = {ingredient, ingredient_a}
            product_id += 1
            ingredient_map[Product(product_id, f"{ingredient} and {ingredient_b} {self.PRODUCT_VARIATION_LIST[2]}")] = {ingredient, ingredient_b}
            product_id += 1
            ingredient_map[Product(product_id, f"{ingredient}, {ingredient_a} and {ingredient_c} {self.PRODUCT_VARIATION_LIST[1]}")] = {ingredient, ingredient_a, ingredient_c}
            product_id += 1

        products = list(ingredient_map.keys())
        for product in products:
            cleaning_duration_map = {}
            ingredients = ingredient_map[product]
            for previous_product in products:
                no_cleaning = ingredients.issuperset(ingredient_map[previous_product])
                if product == previous_product:
                    cleaning_minutes = 0
                elif no_cleaning:
                    cleaning_minutes = no_cleaning_minutes
                else:
                    cleaning_minutes = cleaning_minutes_minimum + random.randint(0, cleaning_minutes_maximum - cleaning_minutes_minimum)
                cleaning_duration_map[previous_product] = timedelta(minutes=cleaning_minutes)
            product.cleaning_durations = cleaning_duration_map

        solution.products = products

        lines = []
        for i in range(self.line_count):
            name = f"Line {i + 1}"
            operator = f"Operator {chr(ord('A') + (i // 2))}"
            lines.append(Line(i, name, operator, start_date_time))
        solution.lines = lines

        jobs = []
        for i in range(self.job_count):
            product = random.choice(products)
            name = product.name
            duration = timedelta(minutes=job_duration_minutes_minimum + 
                               random.randint(0, job_duration_minutes_maximum - job_duration_minutes_minimum))
            
            target_day_index = (i // self.line_count) * average_cleaning_and_job_duration_minutes // (24 * 60)
            min_start_time = datetime.combine(
                start_date + timedelta(days=random.randint(0, max(0, target_day_index - 2))),
                time.min
            )
            ideal_end_time = datetime.combine(
                start_date + timedelta(days=target_day_index + random.randint(0, 2)),
                time(16, 0)
            )
            max_end_time = ideal_end_time + timedelta(days=1 + random.randint(0, 2))
            
            jobs.append(Job(
                i, name, product, duration, min_start_time, 
                ideal_end_time, max_end_time, 1, False
            ))
        
        jobs.sort(key=lambda job: job.id)
        solution.jobs = jobs

        return solution

    def _next_weekday(self, d, weekday):
        """ weekday: 0 = Monday, 1=Tuesday, etc. """
        days_ahead = weekday - d.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        return d + timedelta(days_ahead)