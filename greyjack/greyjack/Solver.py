
import orjson
import time
import random

from greyjack.agents.base.GJSolution import GJSolution
from greyjack.agents.base.Individual import Individual
from pathos.multiprocessing import ProcessPool
from pathos.threading import ThreadPool
import multiprocessing
from multiprocessing import Pipe
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
        "available_ports" and "default_port" are ignoring on Linux.
        On Windows interprocessing communication is organized by ZMQ, because of "spawn" process creation (needs to bind n_jobs + 1 ports).
        On Linux GreyJack uses Pipes and "fork" mechanism. That's why, you don't need to bind additional ports
        inside Docker container or some Linux VM (useful (and moreover needful) in production environment).
        Windows version of GreyJack is useful for prototyping and keeps universality of solver (keeps possibility for using on Windows).

        parallelization_backend = "threading" for debugging
        parallelization_backend = "processing" for production
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

        self.agent_statuses = {}
        self.observers = []

        self.is_windows = True if "win" in current_platform else False

        self._build_logger()
        if self.is_windows:
            self._init_agents_available_addresses_and_ports()
        else:
            self._init_master_solver_pipe()

    
    def _build_logger(self):

        if self.logging_level is None:
            self.logging_level = "info"
        if self.logging_level not in ["info", "trace", "warn"]:
            raise Exception("logging_level must be in [\"info\", \"trace\", \"warn\"]")
        
        self.logger = logging.getLogger("logger")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s, %(levelname)s: %(message)s', datefmt="%Y/%m/%d %H:%M:%S")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        pass

    def _init_agents_available_addresses_and_ports(self):
        minimal_ports_count_required = self.n_jobs + 1
        if self.available_ports is not None:
            available_ports_count = len(self.available_ports)
            if available_ports_count < minimal_ports_count_required:
                exception_string = "For {} agents required at least {} available ports. Set available_ports list manually or set it None for auto allocation".format(self.n_jobs, minimal_ports_count_required)
                raise Exception(exception_string)
        else:
            self.available_ports = [str(int(self.default_port) + i) for i in range(minimal_ports_count_required)]
        
        self.address = "localhost"
        self.port = self.available_ports[0]
        self.full_address = "tcp://{}:{}".format(self.address, self.port)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # process only the most actual messages from agents (drop old messages)
        self.socket.setsockopt(zmq.CONFLATE, 1)
        self.socket.bind( self.full_address )

        current_port_id = 1
        available_agent_ports = [self.available_ports[current_port_id + i] for i in range(self.n_jobs)]
        self.available_agent_ports = available_agent_ports
        self.available_agent_addresses = ["localhost" for i in range(self.n_jobs)]

        pass

    def _init_master_solver_pipe(self):
        solver_updates_sender, solver_updates_receiver = Pipe()
        self.solver_updates_receiver = solver_updates_receiver
        self.solver_updates_sender = solver_updates_sender


    def solve(self):

        agents = self._setup_agents()
        agents_process_pool = self._run_jobs(agents)
        #self._subscribe_for_new_solutions()

        start_time = time.perf_counter()
        steps_count = 0
        current_best_candidate = None
        while True:

            if self.is_windows:
                agent_publication = self.socket.recv()
                agent_publication = orjson.loads(agent_publication)
            else:
                agent_publication = self.solver_updates_receiver.recv()
            agent_id = agent_publication["agent_id"]
            agent_status = agent_publication["status"]
            local_step = agent_publication["step"]
            solution_candidate = agent_publication["candidate"]
            solution_candidate = Individual.from_list(solution_candidate)

            new_best_flag = False
            if current_best_candidate is None:
                current_best_candidate = solution_candidate
            elif solution_candidate < current_best_candidate:
                current_best_candidate = solution_candidate
                new_best_flag = True
            total_time = time.perf_counter() - start_time
            steps_count += 1
            new_best_string = "New best score!" if new_best_flag else ""
            if self.logging_level == "trace":
                self.logger.info(f"Solutions received: {steps_count} Best score: {current_best_candidate.score}, Solving time: {total_time:.6f}, {new_best_string}, Current (agent: {agent_id}, status: {agent_status}, local_step: {local_step}): {solution_candidate.score}")
            elif self.logging_level == "info":
                self.logger.info(f"Solutions received: {steps_count} Best score: {current_best_candidate.score}, Solving time: {total_time:.6f} {new_best_string}")

            if len(self.observers) >= 1:
                self._notify_observers(current_best_candidate)

            self.agent_statuses[agent_id] = agent_status
            someone_alive = False
            for agent_id in self.agent_statuses:
                current_agent_status = self.agent_statuses[agent_id]
                if current_agent_status == "alive":
                    someone_alive = True
                    break

            if someone_alive is False:
                agents_process_pool.terminate()
                agents_process_pool.close()
                agents_process_pool.join()

                #atexit.register(agents_process_pool.close)
                del agents_process_pool
                gc.collect()
                break

        #current_best_candidate = self._build_gjsolution_from_individual(current_best_candidate)

        return current_best_candidate     

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
            self.agent_statuses[str(i)] = "alive"

        for i in range(self.n_jobs):
            for j in range(self.n_jobs):
                agents[i].round_robin_status_dict[agents[j].agent_id] = deepcopy(agents[i].agent_status)

        if self.is_windows:
            for i in range(self.n_jobs):
                agents[i].solver_master_address = deepcopy(self.full_address)
                agents[i].current_agent_address = deepcopy("tcp://{}:{}".format(self.available_agent_addresses[i], self.available_agent_ports[i]))

            for i in range(self.n_jobs):
                next_agent_id = (i + 1) % self.n_jobs
                agents[i].next_agent_address = deepcopy(agents[next_agent_id].current_agent_address)
        else:
            agents_updates_senders = []
            agents_updates_receivers = []
            for i in range(self.n_jobs):
                updates_sender, updates_receiver = Pipe()
                agents_updates_senders.append(updates_sender)
                agents_updates_receivers.append(updates_receiver)
            agents_updates_receivers.append(agents_updates_receivers.pop(0))

            for i in range(self.n_jobs):
                agents[i].updates_sender = agents_updates_senders[i]
                agents[i].updates_receiver = agents_updates_receivers[i]
                agents[i].solver_master_sender = deepcopy(self.solver_updates_sender)

        return agents

    """def _build_gjsolution_from_individual(self, individual):
        variables_dict = self.score_requesters[0].variables_manager.inverse_transform_variables(individual.transformed_values)
        solution_score = individual.score
        gjsolution = GJSolution(variables_dict, solution_score)
        return gjsolution

    
    def register_observer(self, observer):
        self.observers.append(observer)
        pass

    def _notify_observers(self, solution_update):
        gjsolution = self._build_gjsolution_from_individual(solution_update)
        for observer in self.observers:
            observer.update_solution(gjsolution)
        pass"""