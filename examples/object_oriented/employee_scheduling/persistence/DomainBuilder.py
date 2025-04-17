
import random
import traceback

from greyjack.persistence.DomainBuilderBase import DomainBuilderBase
from examples.object_oriented.employee_scheduling.persistence.demo_data import *

class DomainBuilder(DomainBuilderBase):

    def __init__(self, random_seed=45, dataset_size="large"):
        super().__init__()

        self.random_seed = random_seed
        self.dataset_size = dataset_size

    def build_domain_from_scratch(self):

        if self.dataset_size == "large":
            parameters = demo_data_to_parameters[DemoData.LARGE]
        elif self.dataset_size == "small":
            parameters = demo_data_to_parameters[DemoData.SMALL]
        else:
            raise Exception("dataset_size must be \"large\" or \"small\"")
        initial_schedule = generate_demo_data(parameters)

        domain = initial_schedule

        return domain
    
    def build_from_solution(self, solution, initial_domain=None):

        if initial_domain is None:
            domain = self.build_domain_from_scratch()
        else:
            raise Exception("Not implemented")
        
        for shift_key in solution.variable_values_dict.keys():
            employee_id = solution.variable_values_dict[shift_key]
            shift_id = int(shift_key.split("-->")[0].split(" ")[1])
            domain.shifts[shift_id].employee = employee_id

        return domain

    def build_from_domain(self, domain):
        return super().build_from_domain(domain)


