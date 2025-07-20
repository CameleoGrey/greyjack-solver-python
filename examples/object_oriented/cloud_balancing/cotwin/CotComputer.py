

from greyjack.score_calculation.greynet.greynet_fact import greynet_fact

@greynet_fact
class CotComputer():

    def __init__(self, computer_id, cpu_power, memory_size, network_bandwidth, cost):

        self.computer_id = computer_id
        self.cpu_power = cpu_power
        self.memory_size = memory_size
        self.network_bandwidth = network_bandwidth
        self.cost = cost
    
    def build_from_domain_computer(domain_computer):

        cot_computer = CotComputer(
            domain_computer.computer_id,
            domain_computer.cpu_power,
            domain_computer.memory_size,
            domain_computer.network_bandwidth,
            domain_computer.cost,
        )

        return cot_computer