


class ScheduleCB():

    def __init__(self, computers, processes):
        
        self.computers = computers
        self.processes = processes
    

    def print_metrics(self):

        used_resources_map = {}
        for process in self.processes:
            process_id  = process.process_id
            cpu_power_req  = process.cpu_power_req
            memory_size_req  = process.memory_size_req
            network_bandwidth_req  = process.network_bandwidth_req
            computer_id  = process.computer_id

            if computer_id not in used_resources_map:
                used_resources_map[computer_id] = {
                    "processes": [],
                    "cpu": 0,
                    "memory": 0,
                    "network": 0
                }
            
            used_resources_map[computer_id]["processes"].append(process_id)
            used_resources_map[computer_id]["cpu"] += cpu_power_req
            used_resources_map[computer_id]["memory"] += memory_size_req
            used_resources_map[computer_id]["network"] += network_bandwidth_req
        
        total_violations = 0
        computer_ids = list(sorted(list(used_resources_map.keys())))
        for computer_id in computer_ids:
            computer_info = self.computers[computer_id]

            if used_resources_map[computer_id]["cpu"] > computer_info.cpu_power:
                total_violations += 1
            if used_resources_map[computer_id]["memory"] > computer_info.memory_size:
                total_violations += 1
            if used_resources_map[computer_id]["network"] > computer_info.network_bandwidth:
                total_violations += 1

            print("Computer {} utilization: ".format(computer_id))
            print("    CPU: {} / {} | RAM: {} / {} | NTWRK: {} / {}".format(
                used_resources_map[computer_id]["cpu"], computer_info.cpu_power,
                used_resources_map[computer_id]["memory"], computer_info.memory_size,
                used_resources_map[computer_id]["network"], computer_info.network_bandwidth,
            ))
            print("    PIDs: {}".format(", ".join(str(pid) for pid in used_resources_map[computer_id]["processes"])))
            print()
            print()

        print("Total violations: {}".format(total_violations))
        print("Computers used: {}".format(len(computer_ids)))
        print()
            


