
import pickle
import time
import random
import uuid

from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents.base.GJSolution import GJSolution
from greyjack.agents.base.individuals.Individual import Individual
from pathos.multiprocessing import ProcessPool
from pathos.threading import ThreadPool
import multiprocessing
from multiprocessing import Pipe, SimpleQueue
from copy import deepcopy
import logging
import zmq
import sys
import gc

current_platform = sys.platform

class SolverOOP():

    def __init__(self, domain_builder, cotwin_builder, agent,
                 parallelization_backend=ParallelizationBackend.Multiprocessing, 
                 logging_level=LoggingLevel.Info, 
                 n_jobs=None, score_precision=None,
                 available_ports=None, default_port="25000",
                 initial_solution = None):
        
        """
        On Linux platform solver needs 2 ports to bind.
        On other platforms n_agents + 2.
        All ports are binding to localhost. 

        TODO:
        Create and run 2 Docker containers, that will bind same internal (localhost) ports.
        Will them work simultaneously or someone (both) fall down?
        In theory, containers have theyr own network spaces.
        If Docker can bind the same ports of localhost in different containers
        for internal interprocess communication, then I don't need to care
        about internally binded ports count (only about exposed on the level of API facade).
        """
        
        self.domain_builder = domain_builder
        self.cotwin_builder = cotwin_builder
        self.agent = agent
        self.n_jobs = multiprocessing.cpu_count() // 2 if n_jobs is None else n_jobs
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

        self.is_linux = True if "linux" in current_platform else False

        self._build_logger()
        self._init_master_pub_sub()
        if self.is_linux:
            self._init_master_solver_pipe()
        else:
            self._init_agents_available_addresses_and_ports()

    
    def _build_logger(self):

        if self.logging_level is None:
            self.logging_level = LoggingLevel.Info
        if self.logging_level not in [LoggingLevel.FreshOnly, LoggingLevel.Info, LoggingLevel.Warn]:
            raise Exception("logging_level must be value of LoggingLevel enum from greyjack.agents.base module")
        
        self.logger = logging.getLogger("logger")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s, %(levelname)s: %(message)s', datefmt="%Y/%m/%d %H:%M:%S")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        pass

    def _init_master_pub_sub(self):

        minimal_ports_count_required = 2
        if self.available_ports is not None:
            available_ports_count = len(self.available_ports)
            if available_ports_count < minimal_ports_count_required:
                exception_string = "Required at least {} available ports for master node to share global state between agents. Set available_ports list manually or set it None for auto allocation".format(self.n_jobs, minimal_ports_count_required)
                raise Exception(exception_string)
        else:
            if not self.is_linux:
                minimal_ports_count_required += self.n_jobs
            self.available_ports = [str(int(self.default_port) + i) for i in range(minimal_ports_count_required)]
        
        self.address = "localhost"
        self.master_subscriber_address = "tcp://{}:{}".format(self.address, self.available_ports[0])
        self.context = zmq.Context()
        self.master_to_agents_subscriber_socket = self.context.socket(zmq.SUB)
        self.master_to_agents_subscriber_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # process only the most actual messages from agents (drop old messages)
        self.master_to_agents_subscriber_socket.setsockopt(zmq.CONFLATE, 1)
        self.master_to_agents_subscriber_socket.bind( self.master_subscriber_address )

        self.master_publisher_address = "tcp://{}:{}".format(self.address, self.available_ports[1])
        self.master_to_agents_publisher_socket = self.context.socket(zmq.PUB)
        self.master_to_agents_publisher_socket.bind( self.master_publisher_address )

    def _init_agents_available_addresses_and_ports(self):

        minimal_ports_count_required = self.n_jobs + 2 # including master ports
        if self.available_ports is not None:
            available_ports_count = len(self.available_ports)
            if available_ports_count < minimal_ports_count_required:
                exception_string = "For {} agents required at least {} available ports. Set available_ports list manually or set it None for auto allocation".format(self.n_jobs, minimal_ports_count_required)
                raise Exception(exception_string)
        else:
            self.available_ports = [str(int(self.default_port) + i) for i in range(minimal_ports_count_required)]

        current_port_id = 2
        available_agent_to_agent_ports = [self.available_ports[current_port_id + i] for i in range(self.n_jobs)]
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


    def solve(self):

        agents = self._setup_agents()
        agents_process_pool = self._run_jobs(agents)

        start_time = time.perf_counter()
        steps_count = 0
        while True:

            received_individual, agent_id, agent_status, local_step = self.receive_agent_publication()
            new_best_flag = False
            if self.global_top_individual is None:
                self.global_top_individual = received_individual
            elif received_individual < self.global_top_individual:
                self.global_top_individual = received_individual
                self.update_global_top_solution()
                new_best_flag = True
            self.send_global_update(is_end=False)

            total_time = time.perf_counter() - start_time
            steps_count += 1
            new_best_string = "New best score!" if new_best_flag else ""
            if self.logging_level == LoggingLevel.FreshOnly and new_best_flag:
                self.logger.info(f"Agent: {agent_id:4} Step {local_step} Best score: {self.global_top_individual.score}, Solving time: {total_time:.6f} {new_best_string}")

            if len(self.observers) >= 1:
                self._notify_observers(self.global_top_individual)

            self.agent_statuses[agent_id] = agent_status
            someone_alive = False
            for agent_id in self.agent_statuses:
                current_agent_status = self.agent_statuses[agent_id]
                if current_agent_status == "alive":
                    someone_alive = True
                    break

            if someone_alive is False:
                self.send_global_update(is_end=True)
                agents_process_pool.terminate()
                agents_process_pool.join()
                agents_process_pool.close()
                del agents_process_pool
                
                # to prevent port binding errors in multistage scenario
                del self.context
                del self.master_to_agents_publisher_socket
                del self.master_to_agents_subscriber_socket

                gc.collect()
                break

        return self.global_top_solution     

    def _run_jobs(self, agents):
        def run_agent_solving(agent):
            agent.solve()

        pool_name = str(uuid.uuid4())
        if self.parallelization_backend == ParallelizationBackend.Threading:
            agents_process_pool = ThreadPool(id=pool_name)
        elif self.parallelization_backend == ParallelizationBackend.Multiprocessing:
            agents_process_pool = ProcessPool(id=pool_name)
        else:
            raise Exception("parallelization_backend must be value of enum ParallelizationBackend from greyjack.agents.base module")
        agents_process_pool.ncpus = self.n_jobs
        agents_process_pool.imap(run_agent_solving, agents)

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
            agents[i].total_agents_count = self.n_jobs
            self.agent_statuses[str(i)] = "alive"

        for i in range(self.n_jobs):
            for j in range(self.n_jobs):
                agents[i].round_robin_status_dict[agents[j].agent_id] = deepcopy(agents[i].agent_status)

        for i in range(self.n_jobs):
            agents[i].master_subscriber_address = deepcopy(self.master_subscriber_address)
            agents[i].master_publisher_address = deepcopy(self.master_publisher_address)

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

    def receive_agent_publication(self):

        agent_publication = self.master_to_agents_subscriber_socket.recv()
        agent_publication = pickle.loads(agent_publication)
        agent_id = agent_publication["agent_id"]
        agent_status = agent_publication["status"]
        local_step = agent_publication["step"]
        score_variant = agent_publication["score_variant"]
        received_individual = agent_publication["candidate"]
        received_individual = Individual.get_related_individual_type_by_value(score_variant).from_list(received_individual)
        if not self.is_variables_info_received:
            self.variable_names = agent_publication["variable_names"]
            self.discrete_ids = agent_publication["discrete_ids"]
            self.is_variables_info_received = True

        return received_individual, agent_id, agent_status, local_step

    def send_global_update(self, is_end):

        if self.is_agent_wins_from_comparing_with_global:
            master_publication = [self.global_top_individual.as_list(), self.is_variables_info_received, is_end]
        else:
            master_publication = [None, self.is_variables_info_received, is_end]

        master_publication = pickle.dumps(master_publication)
        self.master_to_agents_publisher_socket.send( master_publication )

    def update_global_top_solution(self):
        individual_list = self.global_top_individual.as_list()
        self.global_top_solution = GJSolution(self.variable_names, self.discrete_ids, individual_list[0], individual_list[1], self.score_precision)
        pass

    
    def register_observer(self, observer):
        self.observers.append(observer)
        pass

    def _notify_observers(self):
        for observer in self.observers:
            observer.update_solution(self.global_top_solution)
        pass