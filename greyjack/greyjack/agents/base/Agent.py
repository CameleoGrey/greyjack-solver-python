
import numpy as np
import logging
import math
import orjson
import time
import zmq
import sys

from greyjack.agents.termination_strategies import *
from greyjack.score_calculation.score_requesters import OOPScoreRequester
from greyjack.score_calculation.score_calculators import PlainScoreCalculator, IncrementalScoreCalculator
from greyjack.agents.base.individuals.Individual import Individual

current_platform = sys.platform

class Agent():

    def __init__(self, migration_rate, migration_frequency, termination_strategy):

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
        self.agent_status = "alive"
        self.round_robin_status_dict = {}
        self.total_agents_count = None

        # windows updates send/receive
        self.context = None
        self.socket_request = None
        self.socket_reply = None
        self.socket_publisher = None
        self.solver_master_address = None
        self.current_agent_address = None
        self.next_agent_address = None

        # linux updates send/receive
        self.updates_sender = None
        self.updates_receiver = None
        self.solver_updates_sender = None

        self.is_windows = True if "win" in current_platform else False

    def _build_logger(self):

        if self.logging_level is None:
            self.logging_level = "info"
        if self.logging_level not in ["info", "trace", "warn"]:
            raise Exception("logging_level must be in [\"info\", \"trace\", \"warn\"]")
        
        self.logger = logging.getLogger("logger_{}".format(self.agent_id))
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s, %(levelname)s: %(message)s', datefmt="%Y/%m/%d %H:%M:%S")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        pass

    def _build_cotwin(self):
        if self.initial_solution is None:
            is_already_initialized = False
            domain = self.domain_builder.build_domain_from_scratch()
        elif isinstance(self.initial_solution, str):
            is_already_initialized = True
            domain = self.domain_builder.build_from_solution(self.initial_solution)
        else:
            is_already_initialized = True
            domain = self.domain_builder.build_from_domain(self.initial_solution)

        self.cotwin = self.cotwin_builder.build_cotwin(domain, is_already_initialized)
    
    def _define_individual_type(self):
        self.score_variant = self.cotwin.score_calculator.score_variant
        self.individual_type = Individual.get_related_individual_type(self.cotwin.score_calculator.score_variant)
    
    # implements by concrete metaheuristics
    def _build_metaheuristic_base(self):
        pass

    def solve(self):

        if self.is_windows:
            self.context = zmq.Context()
            self.socket_request = self.context.socket(zmq.REQ)
            #self.socket_request.RCVTIMEO = 1000
            self.socket_reply = self.context.socket(zmq.REP)
            #self.socket_reply.RCVTIMEO = 1000
            self.socket_reply.bind( self.current_agent_address )
            self.socket_publisher = self.context.socket(zmq.PUB)
            #self.socket_publisher.setsockopt(zmq.CONFLATE, 1)
            self.socket_publisher.connect(self.solver_master_address)

        try:
            self._build_cotwin()
            self._define_individual_type()
            self._build_metaheuristic_base()
            self._build_logger()
            self.init_population()
            self.population.sort()
            self.agent_top_individual = self.population[0]

            self.agent_status = "alive"
            self.steps_to_send_updates = self.migration_frequency
            self.termination_strategy.update( self )
        except Exception as e:
            print(e)
            exit(-1)

        step_id = 0
        while True:
            start_time = time.perf_counter()
            try:
                if self.agent_status == "alive":
                    if self.cotwin.score_calculator.is_incremental: 
                        self.step_incremental()
                    else: 
                        self.step_plain()
            except Exception as e:
                print(e)
                exit(-1)
            
            try:
                step_id += 1
                self.population.sort()
                self.agent_top_individual = self.population[0]
                self.termination_strategy.update( self )
                total_time = time.perf_counter() - start_time
                #print("total_step_time: {}".format(total_time))
                if self.logging_level in ["trace"] and self.agent_status == "alive":
                    self.logger.info(f"Agent: {self.agent_id} Step: {step_id} Global best: {self.agent_top_individual.score}, Step time: {total_time:.6f}")

                if self.total_agents_count > 1:
                    self.steps_to_send_updates -= 1
                    if self.steps_to_send_updates <= 0:
                        self.send_receive_updates()

                if self.termination_strategy.is_accomplish():
                    self.agent_status = "dead"
                    self.round_robin_status_dict[self.agent_id] = self.agent_status
                
                self.send_candidate_to_master(step_id)
            except Exception as e:
                print(e)
                exit(-1)
    
    def init_population(self):

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

    def step_plain(self):
        new_population = []
        samples = self.metaheuristic_base.sample_candidates_plain(self.population, self.agent_top_individual, self.score_requester.variables_manager)
        scores = self.score_requester.request_score_plain(samples)
        if self.score_precision is not None:
            for score in scores:
                score.round(self.score_precision)

        candidates = [self.individual_type(samples[i].copy(), scores[i]) for i in range(len(samples))]
        new_population = self.metaheuristic_base.build_updated_population(self.population, candidates)

        self.population = new_population

    def step_incremental(self):
        new_population = []
        sample, deltas = self.metaheuristic_base.sample_candidates_incremental(self.population, self.agent_top_individual, self.score_requester.variables_manager)
        scores = self.score_requester.request_score_incremental(sample, deltas)
        if self.score_precision is not None:
            for score in scores:
                score.round(self.score_precision)

        new_population = self.metaheuristic_base.build_updated_population_incremental(self.population, sample, deltas, scores)
        self.population = new_population

    def send_receive_updates(self):
        if self.is_windows:
            self._send_receive_updates_windows()
        else:
            self._send_receive_updates_linux()

    def _send_receive_updates_windows(self):
        try:
            if int(self.agent_id) % 2 == 0:
                self._send_updates_windows()
                self._get_updates_windows()
            else:
                self._get_updates_windows()
                self._send_updates_windows()
            self.steps_to_send_updates = self.migration_frequency
        except Exception as e:
            self.logger.info("Agent {} failed to send/receive updates: {}".format(self.agent_id, e))

    def _send_updates_windows(self):

        ready_to_send_request = orjson.dumps( "ready to send updates" )
        self.socket_request.connect(self.next_agent_address)
        self.socket_request.send( ready_to_send_request )
        #request_count_limit = 3
        #current_retries_count = 0
        while True:
            if (self.socket_request.poll(100) & zmq.POLLIN) != 0:
                reply = self.socket_request.recv()
                if isinstance( reply, bytes ):
                    if self.logging_level in ["trace"]:
                        self.logger.info("Agent {} is ready to receive updates".format(orjson.loads(reply)))
                    break
                else:
                    if self.logging_level in ["trace"]:
                        self.logger.info("Waiting for readiness to receive updates")
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
        if self.metaheuristic_base.metaheuristic_name == "LSHADE":
            if len(self.history_archive) > 0:
                rand_id = self.generator.integers(0, len(self.history_archive), 1)[0]
                request["history_archive"] = self.history_archive[rand_id].as_list()
                #request["history_archive"] = self.history_archive[-1]
            else:
                request["history_archive"] = None

        request_serialized = orjson.dumps(request)
        try:
            self.socket_request.connect(self.next_agent_address)
            self.socket_request.send( request_serialized )
            reply = self.socket_request.recv()
        except Exception as e:
            if self.logging_level in ["warn", "trace", "info"]:
                self.logger.error(e)
            return
        reply = orjson.loads( reply )

        return reply

    def _get_updates_windows(self):

        try:
            request_for_sending_updates = self.socket_reply.recv()
        except Exception as e:
            if self.logging_level in ["warn", "trace", "info"]:
                self.logger.error(e)
                self.logger.error("failed to receive")
            self.socket_reply.send(orjson.dumps("Failed to receive updates"))
            return
        self.socket_reply.send(orjson.dumps("{}".format(self.agent_id)))

        try:
            updates_reply = self.socket_reply.recv()
        except Exception as e:
            if self.logging_level in ["warn", "trace", "info"]:
                self.logger.error(e)
                self.logger.error("failed to receive")
            self.socket_reply.send(orjson.dumps("Failed to receive updates"))
            return
        self.socket_reply.send(orjson.dumps("Successfully received updates"))
        updates_reply = orjson.loads( updates_reply )

        if self.metaheuristic_base.metaheuristic_name == "LSHADE":
            history_migrant = updates_reply["history_archive"]
            if (history_migrant is not None and len(self.history_archive) > 0):
                history_migrant = self.individual_type.from_list(history_migrant)
                rand_id = self.generator.integers(0, len(self.history_archive), 1)[0]
                #if updates_reply["history_archive"] < self.history_archive[-1]:
                if history_migrant < self.history_archive[rand_id]:
                    self.history_archive[rand_id] = history_migrant

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

    def _send_receive_updates_lixux(self):
        try:
            if int(self.agent_id) % 2 == 0:
                self._send_updates_linux()
                self._get_updates_linux()
            else:
                self._get_updates_linux()
                self._send_updates_linux()
            self.steps_to_send_updates = self.migration_frequency
        except Exception as e:
            self.logger.info("Agent {} failed to put/receive updates: {}".format(self.agent_id, e))
    
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
        if self.metaheuristic_base.metaheuristic_name == "LSHADE":
            if len(self.history_archive) > 0:
                rand_id = self.generator.integers(0, len(self.history_archive), 1)[0]
                request["history_archive"] = self.history_archive[rand_id].as_list()
                #request["history_archive"] = self.history_archive[-1]
            else:
                request["history_archive"] = None

        try:
            self.updates_sender.send( request )
            reply = self.updates_sender.recv()
        except Exception as e:
            if self.logging_level in ["warn", "trace", "info"]:
                self.logger.error(e)
            return

        return reply
    
    def _get_updates_linux(self):

        try:
            updates_reply = self.updates_receiver.recv()
        except Exception as e:
            if self.logging_level in ["warn", "trace", "info"]:
                self.logger.error(e)
                self.logger.error("failed to receive")
            self.updates_receiver.send("Failed to receive updates")
            return
        self.updates_receiver.send("Successfully received updates")

        if self.metaheuristic_base.metaheuristic_name == "LSHADE":
            history_migrant = updates_reply["history_archive"]
            if (history_migrant is not None and len(self.history_archive) > 0):
                history_migrant = self.individual_type.from_list(history_migrant)
                rand_id = self.generator.integers(0, len(self.history_archive), 1)[0]
                #if updates_reply["history_archive"] < self.history_archive[-1]:
                if history_migrant < self.history_archive[rand_id]:
                    self.history_archive[rand_id] = history_migrant

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

    def send_candidate_to_master(self, step_id):
        if self.is_windows:
                self.send_candidate_to_master_windows(step_id)
        else:
            self.send_candidate_to_master_linux(step_id)

    def send_candidate_to_master_windows(self, step_id):
        agent_publication = {}
        agent_publication["agent_id"] = self.agent_id
        agent_publication["status"] = self.agent_status
        agent_publication["candidate"] = self.agent_top_individual.as_list()
        agent_publication["step"] = step_id
        agent_publication["score_variant"] = self.score_variant
        agent_publication = orjson.dumps( agent_publication )
        self.socket_publisher.send( agent_publication )

    def send_candidate_to_master_linux(self, step_id):
        agent_publication = {}
        agent_publication["agent_id"] = self.agent_id
        agent_publication["status"] = self.agent_status
        agent_publication["candidate"] = self.agent_top_individual.as_list()
        agent_publication["step"] = step_id
        agent_publication["score_variant"] = self.score_variant
        self.socket_publisher.send( agent_publication )
