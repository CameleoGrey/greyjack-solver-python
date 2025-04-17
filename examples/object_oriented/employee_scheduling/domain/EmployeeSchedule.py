

import numpy as np

class EmployeeSchedule():

    def __init__(self, employees, shifts):

        self.employees = employees
        self.shifts = shifts

        pass

    def print_schedule(self):

        for shift in self.shifts:
            shift_assignment_info = str(shift) + " --> " + str(self.employees[shift.employee])
            print(shift_assignment_info)

    def print_metrics(self):

        unfairness_penalty = 0
        m_employees = len(self.employees)
        shifts_counts = np.zeros((m_employees,), np.int64)
        for shift in self.shifts:
            shifts_counts[shift.employee] += 1
        unfairness_penalty += np.sqrt(np.sum(np.square(shifts_counts - shifts_counts.mean())))

        for i in range(m_employees):
            print("{} shifts count: {}".format(self.employees[i].name, shifts_counts[i]))
        print("Mean shifts count: {}".format(shifts_counts.mean()))
        print("Load balance coefficient: {}".format(unfairness_penalty))

