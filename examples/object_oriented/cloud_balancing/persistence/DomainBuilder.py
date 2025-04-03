
import json
from greyjack.persistence.DomainBuilderBase import DomainBuilderBase
from examples.object_oriented.cloud_balancing.domain.Process import Process
from examples.object_oriented.cloud_balancing.domain.Computer import Computer
from examples.object_oriented.cloud_balancing.domain.ScheduleCB import ScheduleCB

class DomainBuilder(DomainBuilderBase):

    def __init__(self, file_path):
        
        super().__init__()
        self.file_path = file_path

        pass

    def build_domain_from_scratch(self):

        with open(self.file_path, "r") as json_file:
            readed_json = json.load(json_file)

        computers = []
        for cumputer_dict in readed_json["computerList"]:
            current_computer = Computer(
                cumputer_dict["id"],
                cumputer_dict["cpuPower"],
                cumputer_dict["memory"],
                cumputer_dict["networkBandwidth"],
                cumputer_dict["cost"],
            )
            computers.append(current_computer)
        

        processes = []
        for process_dict in readed_json["processList"]:
            current_process = Process(
                process_dict["id"],
                process_dict["requiredCpuPower"],
                process_dict["requiredMemory"],
                process_dict["requiredNetworkBandwidth"],
                process_dict["computer"],
            )
            processes.append(current_process)
        
        domain_model = ScheduleCB(computers, processes)
        
        return domain_model

    def build_from_solution(self, solution, initial_domain=None):

        n_processes = len(solution.variable_values_dict.values())
        process_assigned_computer_id_map = [-1 for i in range(n_processes)]
        for assign_name in solution.variable_values_dict.keys():
            computer_id = solution.variable_values_dict[assign_name]
            process_id = int(assign_name.split("-->")[0].split(" ")[-1])
            process_assigned_computer_id_map[process_id] = computer_id

        if initial_domain is None:
            domain_model = self.build_domain_from_scratch()
        else:
            domain_model = initial_domain

        for i in range(n_processes):
            domain_model.processes[i].computer_id = process_assigned_computer_id_map[i]

        return domain_model
    
    def build_from_domain(self, domain):
        return super().build_from_domain(domain)