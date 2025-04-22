
import random
import traceback
from greyjack.persistence.DomainBuilderBase import DomainBuilderBase
from examples.object_oriented.food_packaging.persistence.DemoDataGenerator import DemoDataGenerator

class DomainBuilder(DomainBuilderBase):

    def __init__(self, line_count=5, job_count=100):
        super().__init__()

        self.line_count = line_count
        self.job_count = job_count

    def build_domain_from_scratch(self):
        
        try:
            initial_schedule = DemoDataGenerator(self.line_count, self.job_count).generate_demo_data()
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

        job_id = 0
        line_positions = [[] for line in domain.lines]
        line_job_ids = [[] for line in domain.lines]
        for i in range(0, len(solution_dict), 2):
            line_id = solution_dict[solution_keys[i]]
            line_position = solution_dict[solution_keys[i+1]]
            line_positions[line_id].append( line_position )
            line_job_ids[line_id].append( job_id )
            job_id += 1
        
        jobs = [[] for line in domain.lines]
        for line_id, line_positions_list in enumerate(line_positions):
            line_positions_list = [(i, position) for i, position in enumerate(line_positions_list)]
            line_positions_list = list(sorted(line_positions_list, key=lambda x: x[1]))
            for position_tuple in line_positions_list:
                current_job_id = line_job_ids[line_id][position_tuple[0]]
                jobs[line_id].append( domain.jobs[current_job_id] )
        
        for i, jobs_list in enumerate(jobs):
            domain.lines[i].jobs = jobs_list

        return domain

    def build_from_domain(self, domain):
        return super().build_from_domain(domain)


