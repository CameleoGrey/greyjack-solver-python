
from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger
from examples.object_oriented.cloud_balancing.cotwin.CotScheduleCB import CotScheduleCB
from examples.object_oriented.cloud_balancing.cotwin.CotProcess import CotProcess
from examples.object_oriented.cloud_balancing.cotwin.CotComputer import CotComputer
from examples.object_oriented.cloud_balancing.score.PlainScoreCalculatorCB import PlainScoreCalculatorCB
from examples.object_oriented.cloud_balancing.score.IncrementalScoreCalculatorCB import IncrementalScoreCalculatorCB
import numpy as np
from numba import jit

class CotwinBuilder(CotwinBuilderBase):

    def __init__(self, use_incremental_score_calculator, use_greed_init):

        self.use_incremental_score_calculator = use_incremental_score_calculator
        self.use_greed_init = use_greed_init

        pass

    def build_cotwin(self, domain_model, is_already_initialized):

        cotwin_model = CotScheduleCB()

        cotwin_model.add_planning_entities_list(self._build_planning_processes(domain_model), "processes")
        cotwin_model.add_problem_facts_list(self._build_problem_fact_computers(domain_model), "computers")

        if self.use_incremental_score_calculator:
            score_calculator = IncrementalScoreCalculatorCB()

            #to avoid joining, fast get common info only
            score_calculator.utility_objects["processes_info"] = self._build_processes_common_info(domain_model)
            score_calculator.utility_objects["computers_info"] = self._build_computers_common_info(domain_model)
            score_calculator.utility_objects["computers_costs"] = self._build_computers_costs(domain_model)
        else:
            score_calculator = PlainScoreCalculatorCB()

        cotwin_model.set_score_calculator( score_calculator )

        return cotwin_model
    
    def _build_planning_processes(self, domain_model):

        cot_processes = []
        n_computers = len(domain_model.computers)
        m_processes = len(domain_model.processes)

        if self.use_greed_init:
            initial_computer_ids = self._build_greed_initial_computer_ids(domain_model)
        else:
            initial_computer_ids = m_processes * [None]


        for i, process in enumerate(domain_model.processes):
            cot_process = CotProcess(
                process.process_id,
                process.cpu_power_req,
                process.memory_size_req,
                process.network_bandwidth_req,
                GJInteger(0, n_computers-1, False, initial_computer_ids[i])
            )
            cot_processes.append(cot_process)

        return cot_processes
    
    def _build_greed_initial_computer_ids(self, domain_model):

        processes_info = self._build_processes_common_info(domain_model)
        computers_info = self._build_computers_common_info(domain_model)
        n_processes = len(processes_info)
        m_computers = len(computers_info)

        initial_computer_ids = self._build_initial_ids(n_processes, m_computers, processes_info, computers_info)
        initial_computer_ids = [int(initial_computer_ids[i]) if initial_computer_ids[i] >= 0 else None for i in range(len(initial_computer_ids))]

        
        return initial_computer_ids
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def _build_initial_ids(n_processes, m_computers, processes_info, computers_info):
        initial_computer_ids = np.zeros(n_processes, np.int64) - 1
        current_consumed_resources = np.zeros(3, np.int64)
        assigned_processes_index = [np.zeros(n_processes, np.int64) - 1 for i in range(m_computers)]
        assigned_processes_counts = np.zeros(m_computers, np.int64)
        for process_id in range(n_processes):
            
            acceptable_computer_id = None
            for computer_id in range(m_computers):
                current_consumed_resources = np.zeros(3, np.int64)
                for i in range(assigned_processes_counts[computer_id]):
                    current_consumed_resources += processes_info[assigned_processes_index[computer_id][i]]

                current_consumed_resources += processes_info[process_id]
                resource_deltas = current_consumed_resources - computers_info[computer_id]
                resource_deltas = np.where(resource_deltas > 0, resource_deltas, 0)
                resources_unacceptance = np.sum(resource_deltas)
                if resources_unacceptance == 0:
                    acceptable_computer_id = computer_id
                    assigned_processes_index[computer_id][assigned_processes_counts[computer_id]] = process_id
                    assigned_processes_counts[computer_id] += 1
                    break

            if acceptable_computer_id is not None:
                initial_computer_ids[process_id] = acceptable_computer_id

        return initial_computer_ids
            

    def _build_problem_fact_computers(self, domain_model):

        cot_computers = [CotComputer.build_from_domain_computer(computer) for computer in domain_model.computers]

        return cot_computers
    
    def _build_processes_common_info(self, domain_model):

        n_processes = len(domain_model.processes)
        m_info_fields = 3
        processes_common_info = np.zeros((n_processes, m_info_fields), dtype=np.int64)
        for i in range(n_processes):
            processes_common_info[i][0] = domain_model.processes[i].cpu_power_req
            processes_common_info[i][1] = domain_model.processes[i].memory_size_req
            processes_common_info[i][2] = domain_model.processes[i].network_bandwidth_req
        
        return processes_common_info
    

    def _build_computers_common_info(self, domain_model):

        n_computers = len(domain_model.computers)
        m_info_fields = 3
        computers_common_info = np.zeros((n_computers, m_info_fields), dtype=np.int64)
        for i in range(n_computers):
            computers_common_info[i][0] = domain_model.computers[i].cpu_power
            computers_common_info[i][1] = domain_model.computers[i].memory_size
            computers_common_info[i][2] = domain_model.computers[i].network_bandwidth
        
        return computers_common_info
    
    def _build_computers_costs(self, domain_model):
        
        # to avoid unnecessary slicing while constraints computation
        n_computers = len(domain_model.computers)
        computers_costs = np.zeros((n_computers), dtype=np.int64)
        for i in range(n_computers):
            computers_costs[i] = domain_model.computers[i].cost
        
        return computers_costs