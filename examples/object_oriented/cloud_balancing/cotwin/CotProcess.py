
from greyjack.score_calculation.greynet.greynet_fact import greynet_fact

@greynet_fact
class CotProcess():

    def __init__(self, process_id, cpu_power_req, memory_size_req, network_bandwidth_req, computer_id):

        self.process_id = process_id
        self.cpu_power_req = cpu_power_req
        self.memory_size_req = memory_size_req
        self.network_bandwidth_req = network_bandwidth_req
        self.computer_id = computer_id