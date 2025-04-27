
import random
import traceback
from greyjack.persistence.DomainBuilderBase import DomainBuilderBase
from examples.object_oriented.facility_location.persistence.DemoDataGenerator import DemoDataGenerator

class DomainBuilder(DomainBuilderBase):

    def __init__(self):
        super().__init__()

    def build_domain_from_scratch(self):

        try:
            domain = DemoDataGenerator().generate_demo_data()
        except Exception as e:
            print(traceback.format_exc())

        return domain
    
    def build_from_solution(self, solution, initial_domain=None):

        if initial_domain is None:
            domain = self.build_domain_from_scratch()
        else:
            raise Exception("Not implemented")
        
        for cunsumer_key in solution.variable_values_dict.keys():
            facility_id = solution.variable_values_dict[cunsumer_key]
            cunsumer_id = int(cunsumer_key.split("-->")[0].split(" ")[1])
            domain.consumers[cunsumer_id].facility = domain.facilities[facility_id]

        return domain

    def build_from_domain(self, domain):
        return super().build_from_domain(domain)


