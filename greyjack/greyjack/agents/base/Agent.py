
import numpy as np
import random
import logging
import math
import pickle
import time
import zmq
import sys

from greyjack.agents.termination_strategies import *
from greyjack.agents.base.individuals.Individual import Individual
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.GJSolution import GJSolution
from greyjack.pure_math.MathModel import MathModel

current_platform = sys.platform

class Agent():

    def __init__(self, migration_rate, migration_frequency, termination_strategy, compare_to_global_frequency):

        if termination_strategy is None:
            raise Exception("Agent's termination_strategy is None.")
        self.termination_strategy = termination_strategy

        self.agent_id = None
        self.population_size = None
        self.population = None
        self.individual_type = None
        self.score_variant = None
        self.agent_top_individual = None
        self.logger = None
        self.logging_level = None
        self.domain_builder = None
        self.cotwin_builder = None
        self.cotwin = None
        self.initial_solution = None
        self.score_requester = None

        self.migration_rate = migration_rate
        self.migration_frequency = migration_frequency
        self.steps_to_send_updates = migration_frequency
        self.compare_to_global_frequency = compare_to_global_frequency
        self.steps_to_compare_with_global = compare_to_global_frequency
        self.agent_status = "alive"
        self.is_last_message_shown = False
        self.round_robin_status_dict = {}
        self.total_agents_count = None

        # linux updates send/receive by Pipe (channels) mechanism (doesn't need ports binding, faster, simpler)
        self.agent_to_agent_pipe_sender = None
        self.agent_to_agent_pipe_receiver = None
        self.agent_to_master_updates_sender = None
        self.agent_from_master_updates_receiver = None
        #self.master_publisher_queue = None
        #self.master_subscriber_queue = None

        # platform independent updates send/receive by sockets
        self.context = None
        self.agent_to_agent_socket_sender = None
        self.agent_to_agent_socket_receiver = None
        self.agent_to_master_socket_publisher = None
        self.master_subscriber_address = None
        self.master_publisher_address = None
        self.agent_address_for_other_agents = None
        self.next_agent_address = None
        self.is_master_received_variables_info = False
        self.is_end = False


        self.is_linux = True if "linux" in current_platform else False

    def _build_logger(self):

        if self.logging_level is None:
            self.logging_level = LoggingLevel.Info
        if self.logging_level not in [LoggingLevel.FreshOnly, LoggingLevel.Info, LoggingLevel.Warn]:
            raise Exception("logging_level must be value of LoggingLevel enum from greyjack.agents.base module")
        
        self.logger = logging.getLogger("logger_{}".format(self.agent_id))
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s, %(levelname)s: %(message)s', datefmt="%Y/%m/%d %H:%M:%S")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        pass
    
    def _build_agent_to_master_sockets(self):
        self.context = zmq.Context()

        self.agent_to_master_socket_publisher = self.context.socket(zmq.PUB)
        self.agent_to_master_socket_publisher.connect(self.master_subscriber_address)

        self.agent_to_master_subscriber_socket = self.context.socket(zmq.SUB)
        self.agent_to_master_subscriber_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # process only the most actual messages from agents (drop old messages)
        self.agent_to_master_subscriber_socket.setsockopt(zmq.CONFLATE, 1)
        self.agent_to_master_subscriber_socket.connect( self.master_publisher_address )


    def _build_agent_to_agent_sockets(self):
        self.agent_to_agent_socket_sender = self.context.socket(zmq.REQ)
        self.agent_to_agent_socket_receiver = self.context.socket(zmq.REP)
        self.agent_to_agent_socket_receiver.bind( self.agent_address_for_other_agents )

    def _build_cotwin(self):

        if isinstance(self.domain_builder, MathModel):
            self.cotwin = self.domain_builder
            return

        if self.initial_solution is None:
            is_already_initialized = False
            domain = self.domain_builder.build_domain_from_scratch()
        elif isinstance(self.initial_solution, GJSolution):
            is_already_initialized = True
            domain = self.domain_builder.build_from_solution(self.initial_solution)
        else:
            is_already_initialized = True
            domain = self.domain_builder.build_from_domain(self.initial_solution)

        self.cotwin = self.cotwin_builder.build_cotwin(domain, is_already_initialized)
    
    def _define_individual_type(self):
        if isinstance(self.cotwin, MathModel):
            self.score_variant = self.cotwin.score_variant
        else:
            self.score_variant = self.cotwin.score_calculator.score_variant
        self.individual_type = Individual.get_related_individual_type(self.score_variant)
    
    # implements by concrete metaheuristics
    def _build_metaheuristic_base(self):
        pass

    def solve(self):

        try:
            self._build_agent_to_master_sockets()
            if not self.is_linux:
                self._build_agent_to_agent_sockets()
            self._build_cotwin()
            self._define_individual_type()
            self._build_metaheuristic_base()
            self._build_logger()
            self._init_population()
            self.population.sort()
            self.agent_top_individual = self.population[0]

            self.agent_status = "alive"
            self.steps_to_send_updates = self.migration_frequency
            self.termination_strategy.update( self )
        except Exception as e:
            self.logger.error(f"{e}")
            exit(-1)

        step_id = 0
        start_time = time.perf_counter()
        while True:
            #start_step_time = time.perf_counter()
            try:
                if self.agent_status == "alive":
                    if self.cotwin.score_calculator.is_incremental: 
                        self._step_incremental()
                    else: 
                        self._step_plain()
            except Exception as e:
                self.logger.error(f"{e}")
                exit(-1)
            
            try:
                step_id += 1
                self.population.sort()
                if self.population[0] < self.agent_top_individual:
                    self.agent_top_individual = self.population[0].copy()
                self.termination_strategy.update( self )
                #step_time = time.perf_counter() - start_time
                #print("step_time: {}".format(step_time))
                total_time = time.perf_counter() - start_time
                if self.logging_level == LoggingLevel.Info and self.agent_status == "alive":
                    self.logger.info(f"Agent: {self.agent_id:4} Step: {step_id} Best score: {self.agent_top_individual.score}, Solving time: {total_time:.6f}")

                if self.total_agents_count > 1:
                    self.steps_to_send_updates -= 1
                    if self.steps_to_send_updates <= 0:
                        self._send_receive_updates()

                if self.termination_strategy.is_accomplish():
                    self.agent_status = "dead"
                    self.round_robin_status_dict[self.agent_id] = self.agent_status
                    if not self.is_last_message_shown:
                        self.logger.warning(f"Agent: {self.agent_id:4} has successfully terminated work. Now it's just transmitting updates between its neighbours until at least one agent is alive.")
                        self.is_last_message_shown = True

                self.steps_to_compare_with_global -= 1
                if self.steps_to_compare_with_global <= 0:
                    self._send_candidate_to_master(step_id)

                    if self.is_win_from_comparing_with_global or (not self.is_master_received_variables_info):
                        self._check_global_updates()
                        if self.is_end:
                            return
                    self.steps_to_compare_with_global = self.compare_to_global_frequency
            except Exception as e:
                self.logger.error(f"{e}")
                exit(-1)
    
    def _init_population(self):

        self.population = []
        if not self.cotwin.score_calculator.is_incremental:
            samples = []
            for _ in range(self.population_size):
                generated_sample = self.score_requester.variables_manager.sample_variables()
                samples.append(generated_sample)
            scores = self.score_requester.request_score_plain(samples)

            for i in range(self.population_size):
                self.population.append(self.individual_type(samples[i].copy(), scores[i]))

        else:
            generated_sample = self.score_requester.variables_manager.sample_variables()
            deltas = [[(i, val) for i, val in enumerate(generated_sample)]]
            scores = self.score_requester.request_score_incremental(generated_sample, deltas)
            self.population.append(self.individual_type(generated_sample, scores[0]))

    def _step_plain(self):
        new_population = []
        samples = self.metaheuristic_base.sample_candidates_plain(self.population, self.agent_top_individual)
        scores = self.score_requester.request_score_plain(samples)
        if self.score_precision is not None:
            for score in scores:
                score.round(self.score_precision)

        candidates = [self.individual_type(samples[i].copy(), scores[i]) for i in range(len(samples))]
        new_population = self.metaheuristic_base.build_updated_population(self.population, candidates)

        self.population = new_population

    def _step_incremental(self):
        new_population = []
        sample, deltas = self.metaheuristic_base.sample_candidates_incremental(self.population, self.agent_top_individual)
        scores = self.score_requester.request_score_incremental(sample, deltas)
        if self.score_precision is not None:
            for score in scores:
                score.round(self.score_precision)

        new_population = self.metaheuristic_base.build_updated_population_incremental(self.population, sample, deltas, scores)
        self.population = new_population

    def _send_receive_updates(self):
        if self.is_linux:
            self._send_receive_updates_linux()
        else:
            self._send_receive_updates_universal()

    def _send_receive_updates_universal(self):
        try:
            if int(self.agent_id) % 2 == 0:
                self._send_updates_universal()
                self._get_updates_universal()
            else:
                self._get_updates_universal()
                self._send_updates_universal()
            self.steps_to_send_updates = self.migration_frequency
        except Exception as e:
            self.logger.warning("Agent {} failed to send/receive updates: {}".format(self.agent_id, e))

    def _send_updates_universal(self):

        ready_to_send_request = pickle.dumps( "ready to send updates" )
        self.agent_to_agent_socket_sender.connect(self.next_agent_address)
        self.agent_to_agent_socket_sender.send( ready_to_send_request )
        #request_count_limit = 3
        #current_retries_count = 0
        while True:
            if (self.agent_to_agent_socket_sender.poll(100) & zmq.POLLIN) != 0:
                reply = self.agent_to_agent_socket_sender.recv()
                if isinstance( reply, bytes ):
                    break
                else:
                    continue

        
        # population already sorted after step
        #self.population.sort()
        migrants_count = math.ceil(self.migration_rate * len(self.population))
        if migrants_count <= 0:
            migrants_count = 1

        # assuming that all updates are sorted by agents themselves
        # (individual with id == 0 is best in update-subpopulation)
        migrants = self.population[:migrants_count]
        migrants = self.individual_type.convert_individuals_to_lists(migrants)
        request = {"agent_id": self.agent_id, 
                   "round_robin_status_dict": self.round_robin_status_dict,
                   "request_type": "put_updates", 
                   "migrants": migrants}
        """if self.metaheuristic_base.metaheuristic_name == "LSHADE":
            if len(self.history_archive) > 0:
                rand_id = random.randint(0, len(self.history_archive) - 1)
                request["history_archive"] = self.history_archive[rand_id].as_list()
                #request["history_archive"] = self.history_archive[-1]
            else:
                request["history_archive"] = None"""

        request_serialized = pickle.dumps(request)
        try:
            self.agent_to_agent_socket_sender.connect(self.next_agent_address)
            self.agent_to_agent_socket_sender.send( request_serialized )
            reply = self.agent_to_agent_socket_sender.recv()
        except Exception as e:
            self.logger.error(e)
            return
        reply = pickle.loads( reply )

        return reply

    def _get_updates_universal(self):

        try:
            request_for_sending_updates = self.agent_to_agent_socket_receiver.recv()
        except Exception as e:
            self.logger.error(e)
            self.logger.error("failed to receive update")
            self.agent_to_agent_socket_receiver.send(pickle.dumps("Failed to receive updates"))
            return
        self.agent_to_agent_socket_receiver.send(pickle.dumps("{}".format(self.agent_id)))

        try:
            updates_reply = self.agent_to_agent_socket_receiver.recv()
        except Exception as e:
            self.logger.error(e)
            self.logger.error("failed to receive")
            self.agent_to_agent_socket_receiver.send(pickle.dumps("Failed to receive updates"))
            return
        self.agent_to_agent_socket_receiver.send(pickle.dumps("Successfully received updates"))
        updates_reply = pickle.loads( updates_reply )

        """if self.metaheuristic_base.metaheuristic_name == "LSHADE":
            history_migrant = updates_reply["history_archive"]
            if (history_migrant is not None and len(self.history_archive) > 0):
                history_migrant = self.individual_type.from_list(history_migrant)
                rand_id = random.randint(0, len(self.history_archive) - 1)
                #if updates_reply["history_archive"] < self.history_archive[-1]:
                if history_migrant < self.history_archive[rand_id]:
                    self.history_archive[rand_id] = history_migrant"""

        migrants = updates_reply["migrants"]
        migrants = self.individual_type.convert_lists_to_individuals(migrants)
        n_migrants = len(migrants)

        # population already sorted after step
        #self.population.sort()

        if self.metaheuristic_base.metaheuristic_kind == "Population":
            worst_natives = self.population[-n_migrants:]
            updated_tail = [migrant if migrant.score < native.score else native for migrant, native in zip(migrants, worst_natives)]
            self.population[-n_migrants:] = updated_tail
        elif self.metaheuristic_base.metaheuristic_kind == "LocalSearch":
            best_natives = self.population[:n_migrants]
            updated_tail = [migrant if migrant.score < native.score else native for migrant, native in zip(migrants, best_natives)]
            self.population[:n_migrants] = updated_tail
        else:
            raise Exception("metaheuristic_kind can be only Population or LocalSearch")

        self.round_robin_status_dict = updates_reply["round_robin_status_dict"]
        self.round_robin_status_dict[self.agent_id] = self.agent_status

        pass

    def _send_receive_updates_linux(self):
        try:
            if int(self.agent_id) % 2 == 0:
                self._send_updates_linux()
                self._get_updates_linux()
            else:
                self._get_updates_linux()
                self._send_updates_linux()
            self.steps_to_send_updates = self.migration_frequency
        except Exception as e:
            self.logger.warninig("Agent {} failed to put/receive updates: {}".format(self.agent_id, e))
    
    def _send_updates_linux(self):
        
        # population already sorted after step
        #self.population.sort()
        migrants_count = math.ceil(self.migration_rate * len(self.population))
        if migrants_count <= 0:
            migrants_count = 1

        # assuming that all updates are sorted by agents themselves
        # (individual with id == 0 is best in update-subpopulation)
        migrants = self.population[:migrants_count]
        migrants = self.individual_type.convert_individuals_to_lists(migrants)
        request = {"agent_id": self.agent_id, 
                   "round_robin_status_dict": self.round_robin_status_dict,
                   "request_type": "put_updates", 
                   "migrants": migrants}
        """if self.metaheuristic_base.metaheuristic_name == "LSHADE":
            if len(self.history_archive) > 0:
                rand_id = random.randint(0, len(self.history_archive) - 1)
                request["history_archive"] = self.history_archive[rand_id].as_list()
                #request["history_archive"] = self.history_archive[-1]
            else:
                request["history_archive"] = None"""

        try:
            self.agent_to_agent_pipe_sender.send( request )
            reply = self.agent_to_agent_pipe_sender.recv()
        except Exception as e:
            self.logger.error(e)
            return

        return reply
    
    def _get_updates_linux(self):

        try:
            updates_reply = self.agent_to_agent_pipe_receiver.recv()
        except Exception as e:
            self.logger.error(e)
            self.logger.error("failed to receive")
            self.agent_to_agent_pipe_receiver.send("Failed to receive updates")
            return
        self.agent_to_agent_pipe_receiver.send("Successfully received updates")

        """if self.metaheuristic_base.metaheuristic_name == "LSHADE":
            history_migrant = updates_reply["history_archive"]
            if (history_migrant is not None and len(self.history_archive) > 0):
                history_migrant = self.individual_type.from_list(history_migrant)
                rand_id = random.randint(0, len(self.history_archive) - 1)
                #if updates_reply["history_archive"] < self.history_archive[-1]:
                if history_migrant < self.history_archive[rand_id]:
                    self.history_archive[rand_id] = history_migrant"""

        migrants = updates_reply["migrants"]
        migrants = self.individual_type.convert_lists_to_individuals(migrants)
        n_migrants = len(migrants)

        # population already sorted after step
        #self.population.sort()

        if self.metaheuristic_base.metaheuristic_kind == "Population":
            worst_natives = self.population[-n_migrants:]
            updated_tail = [migrant if migrant.score < native.score else native for migrant, native in zip(migrants, worst_natives)]
            self.population[-n_migrants:] = updated_tail
        elif self.metaheuristic_base.metaheuristic_kind == "LocalSearch":
            best_natives = self.population[:n_migrants]
            updated_tail = [migrant if migrant.score < native.score else native for migrant, native in zip(migrants, best_natives)]
            self.population[:n_migrants] = updated_tail
        else:
            raise Exception("metaheuristic_kind can be only Population or LocalSearch")

        self.round_robin_status_dict = updates_reply["round_robin_status_dict"]
        self.round_robin_status_dict[self.agent_id] = self.agent_status

        pass

    def _send_candidate_to_master(self, step_id):
        self._send_candidate_to_master_universal(step_id)

    def _send_candidate_to_master_universal(self, step_id):
        agent_publication = {}
        agent_publication["agent_id"] = self.agent_id
        agent_publication["status"] = self.agent_status
        agent_publication["candidate"] = self.agent_top_individual.as_list()
        agent_publication["step"] = step_id
        agent_publication["score_variant"] = self.score_variant
        if self.is_master_received_variables_info:
            agent_publication["variable_names"] = None
            agent_publication["discrete_ids"] = None
        else:
            agent_publication["variable_names"] = self.score_requester.variables_manager.get_variables_names_vec()
            agent_publication["discrete_ids"] = self.score_requester.variables_manager.discrete_ids
        agent_publication = pickle.dumps( agent_publication )
        self.agent_to_master_socket_publisher.send( agent_publication )

    def _check_global_updates(self):
        self._check_global_updates_universal()
    


    def _check_global_updates_universal(self):
        master_publication = self.agent_to_master_subscriber_socket.recv()
        master_publication = pickle.loads(master_publication)

        if self.is_win_from_comparing_with_global:
            global_top_individual = master_publication[0]
            global_top_individual = Individual.get_related_individual_type(self.score_variant).from_list(global_top_individual)
            if global_top_individual < self.agent_top_individual:
                self.agent_top_individual = global_top_individual
                self.population[0] = global_top_individual.copy()
        
        is_variable_names_received = master_publication[1]
        self.is_master_received_variables_info = is_variable_names_received
        self.is_end = master_publication[2]