
import random
import traceback

from greyjack.persistence.DomainBuilderBase import DomainBuilderBase
from examples.object_oriented.maintenance_scheduling.persistence.DemoDataGenerator import DemoDataGenerator, DemoData

class DomainBuilder(DomainBuilderBase):

    def __init__(self, dataset_size="small"):
        super().__init__()
        self.dataset_size = dataset_size

    def build_domain_from_scratch(self):
        
        try:
            if self.dataset_size == "large":
                initial_schedule = DemoDataGenerator.generate_demo_data(DemoData.LARGE)
            elif self.dataset_size == "small":
                initial_schedule = DemoDataGenerator.generate_demo_data(DemoData.SMALL)
            else:
                raise Exception("dataset_size must be \"large\" or \"small\"")
        except Exception as e:
            print(traceback.format_exc())


        domain = initial_schedule

        return domain
    
    def build_from_solution(self, solution, initial_domain=None):
        if initial_domain is None:
            domain = self.build_domain_from_scratch()
        else:
            raise Exception("Not implemented")
        
        #print(solution)
        
        solution_dict = solution.variable_values_dict
        solution_keys = list(solution_dict.keys())

        j = 0
        for i in range(0, len(solution_dict), 2):
            crew_id = solution_dict[solution_keys[i]]
            start_date_id = solution_dict[solution_keys[i+1]]

            domain.jobs[j].crew_id = crew_id
            domain.jobs[j].start_date_id = start_date_id
            j += 1

        return domain

    def build_from_domain(self, domain):
        return super().build_from_domain(domain)


