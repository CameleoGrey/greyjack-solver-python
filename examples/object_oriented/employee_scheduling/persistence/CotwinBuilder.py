

import numpy as np
import random
import traceback
from datetime import datetime
from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger
from examples.object_oriented.employee_scheduling.cotwin.Cotwin import Cotwin
from examples.object_oriented.employee_scheduling.cotwin.CotEmployee import CotEmployee
from examples.object_oriented.employee_scheduling.cotwin.CotShift import CotShift
from examples.object_oriented.employee_scheduling.score.IncrementalScoreCalculator import IncrementalScoreCalculator
from examples.object_oriented.employee_scheduling.score.PlainScoreCalculator import PlainScoreCalculator


class CotwinBuilder(CotwinBuilderBase):
    def __init__(self, use_incremental_score_calculator, use_greed_init):
        self.use_incremental_score_calculator = use_incremental_score_calculator
        self.use_greed_init = use_greed_init
        pass

    def build_cotwin(self, domain, is_already_initialized):

        cotwin = Cotwin()

        try:

            planning_shifts = self._build_planning_shifts(domain, is_already_initialized)
            problem_fact_employees = self._build_problem_fact_employees(domain)

            if self.use_incremental_score_calculator:
                score_calculator = IncrementalScoreCalculator()
                self._add_utility_info_for_incremental_scoring(cotwin, score_calculator, planning_shifts, problem_fact_employees)
                self._remove_redundant_fields(planning_shifts)
                cotwin.add_planning_entities_list(planning_shifts, "shifts")
            else:
                score_calculator = PlainScoreCalculator()
                cotwin.add_planning_entities_list(planning_shifts, "shifts")
                cotwin.add_problem_facts_list(problem_fact_employees, "employees")

            cotwin.set_score_calculator( score_calculator )
        except Exception as e:
            print(traceback.format_exc())

        return cotwin
    
    def _remove_redundant_fields(self, planning_shifts):

        redundant_fields = ["start", "end", "start_date", "location", "required_skill"]
        for i in range(len(planning_shifts)):
            for field_name in redundant_fields:
                delattr(planning_shifts[i], field_name)


    
    def _add_utility_info_for_incremental_scoring(self, cotwin, score_calculator, planning_shifts, problem_fact_employees):

        all_skills = set()
        for shift in planning_shifts:
            all_skills.add(shift.required_skill)
        for employee in problem_fact_employees:
            for skill_name in employee.skills:
                all_skills.add(skill_name)
        all_skills = list(sorted(list(all_skills)))
        skills_to_int_map = {}
        for i, skill_name in enumerate(all_skills):
            skills_to_int_map[skill_name] = i
        inverted_skills_to_int_map = { v: k for k, v in skills_to_int_map.items() }

        n_shifts = len(planning_shifts)
        shift_starts = np.zeros((n_shifts, ), np.int64)
        shift_ends = np.zeros((n_shifts, ), np.int64)
        shift_start_dates = np.zeros((n_shifts, ), np.int64)
        shift_req_skills = np.zeros((n_shifts, ), np.int64)
        for i in range(n_shifts):
            shift = planning_shifts[i]
            shift_starts[i] = int(planning_shifts[i].start.timestamp() // 60) # minutes
            shift_ends[i] = int(planning_shifts[i].end.timestamp() // 60)
            shift_start_dates[i] = int(datetime.combine(planning_shifts[i].start_date, datetime.min.time()).timestamp() // 60)
            shift_req_skills[i] = skills_to_int_map[planning_shifts[i].required_skill]
        score_calculator.utility_objects["shift_starts"] = shift_starts.tolist()
        score_calculator.utility_objects["shift_ends"] = shift_starts.tolist()
        score_calculator.utility_objects["shift_start_dates"] = shift_starts.tolist()
        score_calculator.utility_objects["shift_req_skills"] = shift_req_skills.tolist()
        
        m_employees = len(problem_fact_employees)
        employee_skills = []
        employee_unavailable_dates = []
        employee_undesired_dates = []
        employee_desired_dates = []
        for i in range(m_employees):
            employee = problem_fact_employees[i]

            skills = []
            for skill_name in employee.skills:
                skills.append( skills_to_int_map[skill_name] )
            employee_skills.append(np.array(skills, np.int64))

            unavailable_dates = []
            for date in employee.unavailable_dates:
                unavailable_dates.append(int(datetime.combine(date, datetime.min.time()).timestamp() // 60)) # minutes
            employee_unavailable_dates.append(np.array(unavailable_dates, np.int64))

            undesired_dates = []
            for date in employee.undesired_dates:
                undesired_dates.append(int(datetime.combine(date, datetime.min.time()).timestamp() // 60))
            employee_undesired_dates.append(np.array(undesired_dates, np.int64))

            desired_dates = []
            for date in employee.desired_dates:
                desired_dates.append(int(datetime.combine(date, datetime.min.time()).timestamp() // 60))
            employee_desired_dates.append(np.array(desired_dates, np.int64))

        score_calculator.utility_objects["employee_skills"] = employee_skills
        score_calculator.utility_objects["employee_unavailable_dates"] = employee_unavailable_dates
        score_calculator.utility_objects["employee_undesired_dates"] = employee_undesired_dates
        score_calculator.utility_objects["employee_desired_dates"] = employee_desired_dates

        pass
    
    def _build_planning_shifts(self, domain, is_already_initialized):

        if is_already_initialized:
            raise Exception("Using initialized domain not initialized")
        
        if self.use_greed_init:
            raise Exception("greed initialization isn't implemented")
        else:
            n_employees = len(domain.employees)
            initial_employee_ids = [random.randint(0, n_employees-1) for i in range(len(domain.shifts))]
            #random.shuffle(initial_employee_ids)

        planning_shifts = []
        for i, current_shift in enumerate(domain.shifts):
            planning_shifts.append(
                CotShift(
                    id = current_shift.id,
                    start = current_shift.start,
                    end = current_shift.end,
                    location = current_shift.location,
                    required_skill = current_shift.required_skill,
                    employee = GJInteger(0, len(domain.employees)-1, False, initial_employee_ids[i]),
                )
            )
        
        return planning_shifts
    
    def _build_problem_fact_employees(self, domain):

        problem_fact_employees = []
        for id, domain_employee in enumerate(domain.employees):
            problem_fact_employees.append(
                CotEmployee(
                    id=id,
                    name=domain_employee.name,
                    skills=domain_employee.skills,
                    unavailable_dates=domain_employee.unavailable_dates,
                    undesired_dates=domain_employee.undesired_dates,
                    desired_dates=domain_employee.desired_dates,
                )
            )
        
        return problem_fact_employees





