
import orjson
import time
import random

from greyjack.agents.base.GJSolution import GJSolution
from greyjack.agents.base.individuals.Individual import Individual
from greyjack.score_calculation.score_requesters.OOPScoreRequester import OOPScoreRequester
from pathos.multiprocessing import ProcessPool
from pathos.threading import ThreadPool
import multiprocessing as mp
from multiprocessing import Pipe, SimpleQueue
from multiprocessing.shared_memory import ShareableList
from copy import deepcopy
import logging
import zmq
import sys
import gc

current_platform = sys.platform

class Solver():

    def __init__(self, domain_builder, cotwin_builder, agent,
                 n_jobs=None, parallelization_backend="processing",
                 score_precision=None, logging_level=None,
                 available_ports=None, default_port="25000",
                 initial_solution = None):
        
        """
        "available_ports" and "default_port" are ignoring on Linux because of using Pipe (channels) mechanism.
        For other platforms ZMQ sockets are used to keep possibility of using Solver on other platforms.
        Excluding redundant ports binding is neccessary for production environments (usually docker images are using Linux distributions), 
        but not important for prototyping (on Windows, for example). 

        parallelization_backend = "threading" for debugging
        parallelization_backend = "processing" for production
        """
        
        self.domain_builder = domain_builder
        self.cotwin_builder = cotwin_builder
        self.agent = agent
        self.n_jobs = mp.cpu_count() // 2 if n_jobs is None else n_jobs
        self.score_precision = score_precision
        self.logging_level = logging_level
        self.parallelization_backend = parallelization_backend
        self.available_ports = available_ports
        self.default_port = default_port
        self.initial_solution = initial_solution

        self.global_top_individual = None
        self.global_top_solution = None
        self.variable_names = None
        self.discrete_ids = None
        self.is_variables_info_received = False
        self.is_agent_wins_from_comparing_with_global = agent.is_win_from_comparing_with_global
        self.agent_statuses = {}
        self.observers = []

        # neccessary to build here cotwin and score_requester for allocating enough shared memory
        self.agent.domain_builder = domain_builder
        self.agent.cotwin_builder = cotwin_builder
        self.agent._build_cotwin()
        cotwin = self.agent.cotwin
        self.agent.cotwin = None
        self.agent.cotwin_builder = None
        self.agent.domain_builder = None
        score_requester = OOPScoreRequester(cotwin)
        self.variable_names = score_requester.variables_manager.get_variables_names_vec()
        self.discrete_ids = score_requester.variables_manager.discrete_ids.copy()
        self.variables_count = len(self.variable_names)
        cotwin.score_calculator._setup_score_type()
        self.score_len = cotwin.score_calculator.score_type.precision_len()
        self.shared_individual = mp.Array("f", len(self.variable_names) + self.score_len)
        stub_values = cotwin.score_calculator.score_type.get_stub_score()
        self.shared_individual[self.variables_count:] = stub_values.as_list()
        self.shared_round_robin_status = mp.Array("b", self.n_jobs)
        self.shared_round_robin_status[::] = [True for i in range(self.n_jobs)]


        self.is_linux = True if "linux" in current_platform else False

        self._build_logger()
        if self.is_linux:
            self._init_master_solver_pipe()
        else:
            self._init_agents_available_addresses_and_ports()

    
    def _build_logger(self):

        if self.logging_level is None:
            self.logging_level = "info"
        if self.logging_level not in ["info", "trace", "warn", "fresh_only"]:
            raise Exception("logging_level must be in [\"info\", \"trace\", \"warn\", \"fresh_only\"]")
        
        self.logger = logging.getLogger("logger")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s, %(levelname)s: %(message)s', datefmt="%Y/%m/%d %H:%M:%S")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        pass

    def _init_agents_available_addresses_and_ports(self):
        minimal_ports_count_required = self.n_jobs + 2
        if self.available_ports is not None:
            available_ports_count = len(self.available_ports)
            if available_ports_count < minimal_ports_count_required:
                exception_string = "For {} agents required at least {} available ports. Set available_ports list manually or set it None for auto allocation".format(self.n_jobs, minimal_ports_count_required)
                raise Exception(exception_string)
        else:
            self.available_ports = [str(int(self.default_port) + i) for i in range(minimal_ports_count_required)]

        available_agent_to_agent_ports = [self.available_ports[i] for i in range(self.n_jobs)]
        self.available_agent_to_agent_ports = available_agent_to_agent_ports
        self.available_agent_to_agent_addresses = ["localhost" for i in range(self.n_jobs)]

        pass

    def _init_master_solver_pipe(self):
        agent_to_master_updates_sender, master_from_agent_updates_receiver = Pipe()
        self.agent_to_master_updates_sender = agent_to_master_updates_sender
        self.master_from_agent_updates_receiver = master_from_agent_updates_receiver
        master_to_agent_updates_sender, agent_from_master_updates_receiver = Pipe()
        self.master_to_agent_updates_sender = master_to_agent_updates_sender
        self.agent_from_master_updates_receiver = agent_from_master_updates_receiver

        #self.master_publisher_queue = SimpleQueue()
        #self.master_subscriber_queue = SimpleQueue()


    def solve(self):

        agents = self._setup_agents()
        agents_process_pool = self._run_jobs(agents)
        while True:

            # hypothesis: try to copy to not lock each time when accessing shared memory in loop
            # or it will copy shared object itself?
            #shared_round_robin_status = deepcopy(self.shared_round_robin_status)
            shared_round_robin_status = self.shared_round_robin_status
            someone_alive = False
            for is_alive in shared_round_robin_status:
                if is_alive:
                    someone_alive = True
                    break

            if someone_alive is False:
                agents_process_pool.terminate()
                agents_process_pool.close()
                del agents_process_pool
                gc.collect()
                break
        
        global_top_solution = GJSolution(
            self.variable_names, 
            self.discrete_ids, 
            self.shared_individual[:self.variables_count], 
            self.shared_individual[self.variables_count:], 
            self.score_precision
            )
        
        return global_top_solution     

    def _run_jobs(self, agents):
        def run_agent_solving(agent):
            agent.solve()

        if self.parallelization_backend == "threading":
            agents_process_pool = ThreadPool(id="agents_pool")
        elif self.parallelization_backend == "processing":
            agents_process_pool = ProcessPool(id="agents_pool")
        else:
            raise Exception("parallelization_backend can be only \"threading\" (for debugging) or \"processing\" (for production)")
        agents_process_pool.ncpus = self.n_jobs
        agents_process_pool.amap(run_agent_solving, agents)

        return agents_process_pool

    def _setup_agents(self):
        
        agents = [deepcopy(self.agent) for i in range(self.n_jobs)]
        for i in range(self.n_jobs):
            agents[i].agent_id = str(i)
            agents[i].domain_builder = deepcopy(self.domain_builder)
            agents[i].cotwin_builder = deepcopy(self.cotwin_builder)
            agents[i].initial_solution = deepcopy(self.initial_solution)
            agents[i].score_precision = deepcopy(self.score_precision)
            agents[i].logging_level = deepcopy(self.logging_level)
            agents[i].observers = deepcopy(self.observers)
            agents[i].total_agents_count = self.n_jobs

            agents[i].variables_count = self.variables_count
            agents[i].score_len = self.score_len
            agents[i].shared_individual = self.shared_individual
            agents[i].shared_round_robin_status = self.shared_round_robin_status

        if self.is_linux:
            agents_updates_senders = []
            agents_updates_receivers = []
            for i in range(self.n_jobs):
                agent_to_agent_pipe_sender, agent_to_agent_pipe_receiver = Pipe()
                agents_updates_senders.append(agent_to_agent_pipe_sender)
                agents_updates_receivers.append(agent_to_agent_pipe_receiver)
            agents_updates_receivers.append(agents_updates_receivers.pop(0))
            for i in range(self.n_jobs):
                agents[i].agent_to_agent_pipe_sender = agents_updates_senders[i]
                agents[i].agent_to_agent_pipe_receiver = agents_updates_receivers[i]
            
        else:
            for i in range(self.n_jobs):
                agents[i].agent_address_for_other_agents = deepcopy("tcp://{}:{}".format(self.available_agent_to_agent_addresses[i], self.available_agent_to_agent_ports[i]))
            for i in range(self.n_jobs):
                next_agent_id = (i + 1) % self.n_jobs
                agents[i].next_agent_address = deepcopy(agents[next_agent_id].agent_address_for_other_agents)

        return agents
    
    def register_observer(self, observer):
        self.observers.append(observer)
        pass