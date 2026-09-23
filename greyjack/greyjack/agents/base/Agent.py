import logging
import math
import pickle
import time
import zmq
import sys
import uuid

from greyjack.agents.base._lifecycle import AgentCancelled, POLL_SECONDS
from greyjack.agents.base.individuals.Individual import Individual
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.GJSolution import GJSolution
from greyjack.pure_math.MathModel import MathModel

current_platform = sys.platform


class Agent:
    def __init__(
        self,
        migration_rate,
        migration_frequency,
        termination_strategy,
        compare_to_global_frequency,
    ):
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
        # self.master_publisher_queue = None
        # self.master_subscriber_queue = None

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
        self._cancellation = None
        self._lifecycle_events = None
        self._phase = "startup"
        self._last_step = 0
        self._lifecycle_finished = False
        self._logger_handler = None

        self.is_linux = True if "linux" in current_platform else False

    def _build_logger(self):
        if self.logging_level is None:
            self.logging_level = LoggingLevel.Info
        if self.logging_level not in (
            LoggingLevel.FreshOnly,
            LoggingLevel.Info,
            LoggingLevel.Warn,
        ):
            raise ValueError("logging_level must be a LoggingLevel value")
        self.logger = logging.getLogger(
            f"greyjack.agent.{self.agent_id}.{uuid.uuid4().hex}"
        )
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self._logger_handler = logging.StreamHandler()
        self._logger_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s, %(levelname)s: %(message)s", datefmt="%Y/%m/%d %H:%M:%S"
            )
        )
        self.logger.addHandler(self._logger_handler)

    def _new_socket(self, kind):
        socket = self.context.socket(kind)
        socket.setsockopt(zmq.LINGER, 0)
        return socket

    def _build_agent_to_master_sockets(self):
        self.context = zmq.Context()
        self.agent_to_master_socket_publisher = self._new_socket(zmq.PUB)
        self.agent_to_master_socket_publisher.connect(self.master_subscriber_address)
        self.agent_to_master_subscriber_socket = self._new_socket(zmq.SUB)
        self.agent_to_master_subscriber_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.agent_to_master_subscriber_socket.setsockopt(zmq.CONFLATE, 1)
        self.agent_to_master_subscriber_socket.connect(self.master_publisher_address)

    def _build_agent_to_agent_sockets(self):
        self.agent_to_agent_socket_sender = self._new_socket(zmq.REQ)
        self.agent_to_agent_socket_sender.connect(self.next_agent_address)
        self.agent_to_agent_socket_receiver = self._new_socket(zmq.REP)
        self.agent_to_agent_socket_receiver.bind(self.agent_address_for_other_agents)

    def _check_cancellation(self):
        if self.is_end or (
            self._cancellation is not None and self._cancellation.is_set()
        ):
            raise AgentCancelled()

    def _socket_receive(self, socket):
        while True:
            self._check_cancellation()
            if socket.poll(int(POLL_SECONDS * 1000), zmq.POLLIN):
                try:
                    return socket.recv(flags=zmq.NOBLOCK)
                except zmq.Again:
                    pass

    def _socket_send(self, socket, value):
        while True:
            self._check_cancellation()
            try:
                socket.send(value, flags=zmq.NOBLOCK)
                return
            except zmq.Again:
                socket.poll(int(POLL_SECONDS * 1000), zmq.POLLOUT)

    def _pipe_receive(self, connection):
        while True:
            self._check_cancellation()
            if connection.poll(POLL_SECONDS):
                return connection.recv()

    def _pipe_send(self, connection, value):
        self._check_cancellation()
        # Thread endpoints have cancellable puts. Process writes retain Pipe's
        # semantics; a blocked native write is covered by the master's grace limit.
        connection.send(value)

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
        self.individual_type = Individual.get_related_individual_type(
            self.score_variant
        )

    # implements by concrete metaheuristics
    def _build_metaheuristic_base(self):
        pass

    def solve(self):
        try:
            self._phase = "logger setup"
            self._build_logger()
            self._check_cancellation()
            self._phase = "communication setup"
            self._build_agent_to_master_sockets()
            if not self.is_linux:
                self._build_agent_to_agent_sockets()
            self._check_cancellation()
            self._phase = "domain and cotwin construction"
            self._build_cotwin()
            self._check_cancellation()
            self._define_individual_type()
            self._phase = "score requester and metaheuristic construction"
            self._build_metaheuristic_base()
            self._check_cancellation()
            self._phase = "initial scoring"
            self._init_population()
            self._check_cancellation()
            self.population.sort()
            self.agent_top_individual = self.population[0]
            self.agent_status = "alive"
            self.steps_to_send_updates = self.migration_frequency
            # Preserve the existing timer boundary: initial scoring is startup.
            self.termination_strategy.update(self)
            self._emit_lifecycle("initial")
            start_time = time.perf_counter()
            while True:
                self._check_cancellation()
                self._phase = "search step scoring"
                if self.agent_status == "alive":
                    if self.cotwin.score_calculator.is_incremental:
                        self._step_incremental()
                    else:
                        self._step_plain()
                self._check_cancellation()
                self._last_step += 1
                self.population.sort()
                if self.population[0] < self.agent_top_individual:
                    self.agent_top_individual = self.population[0].copy()
                self.termination_strategy.update(self)
                if (
                    self.logging_level == LoggingLevel.Info
                    and self.agent_status == "alive"
                ):
                    self.logger.info(
                        "Agent: %4s Step: %s Best score: %s, Solving time: %.6f",
                        self.agent_id,
                        self._last_step,
                        self.agent_top_individual.score,
                        time.perf_counter() - start_time,
                    )
                # Publish terminal state reliably before another migration wait.
                # Finished agents still relay until all agents finish or cancellation.
                if (
                    self.termination_strategy.is_accomplish()
                    and not self._lifecycle_finished
                ):
                    self.agent_status = "dead"
                    self.round_robin_status_dict[self.agent_id] = "dead"
                    self._lifecycle_finished = True
                    self._emit_lifecycle("finished")
                    self.logger.warning(
                        "Agent: %4s has successfully terminated work; relaying updates until shutdown.",
                        self.agent_id,
                    )
                self._phase = "migration"
                if self.total_agents_count > 1:
                    self.steps_to_send_updates -= 1
                    if self.steps_to_send_updates <= 0:
                        self._send_receive_updates()
                self._phase = "global synchronization"
                self.steps_to_compare_with_global -= 1
                if self.steps_to_compare_with_global <= 0:
                    self._send_candidate_to_master(self._last_step)
                    if (
                        self.is_win_from_comparing_with_global
                        or not self.is_master_received_variables_info
                    ):
                        self._check_global_updates()
                    self.steps_to_compare_with_global = self.compare_to_global_frequency
        except AgentCancelled:
            return
        except Exception:
            if self.logger is not None:
                self.logger.exception(
                    "Agent %s failed during %s", self.agent_id, self._phase
                )
            raise
        finally:
            try:
                if self.agent_top_individual is not None:
                    self._emit_lifecycle("stopped")
            finally:
                self._close_resources()

    def _emit_lifecycle(self, kind):
        if self._lifecycle_events is not None:
            self._lifecycle_events.put(
                pickle.dumps(
                    {
                        "kind": kind,
                        "agent_id": self.agent_id,
                        "publication": self._make_publication(
                            self._last_step, include_metadata=True
                        ),
                    }
                )
            )

    def _close_resources(self):
        for name in (
            "agent_to_master_socket_publisher",
            "agent_to_master_subscriber_socket",
            "agent_to_agent_socket_sender",
            "agent_to_agent_socket_receiver",
        ):
            socket = getattr(self, name, None)
            if socket is not None:
                socket.close(linger=0)
                setattr(self, name, None)
        if self.context is not None:
            self.context.term()
            self.context = None
        for name in ("agent_to_agent_pipe_sender", "agent_to_agent_pipe_receiver"):
            connection = getattr(self, name, None)
            if connection is not None:
                connection.close()
                setattr(self, name, None)
        if self._logger_handler is not None:
            self.logger.removeHandler(self._logger_handler)
            self._logger_handler.close()
            self._logger_handler = None

    def _init_population(self):
        self.population = []
        if not self.cotwin.score_calculator.is_incremental:
            samples = []
            for _ in range(self.population_size):
                generated_sample = (
                    self.score_requester.variables_manager.sample_variables()
                )
                samples.append(generated_sample)
            scores = self.score_requester.request_score_plain(samples)

            for i in range(self.population_size):
                self.population.append(
                    self.individual_type(samples[i].copy(), scores[i])
                )

        else:
            generated_sample = self.score_requester.variables_manager.sample_variables()
            deltas = [[(i, val) for i, val in enumerate(generated_sample)]]
            scores = self.score_requester.request_score_incremental(
                generated_sample, deltas
            )
            self.population.append(self.individual_type(generated_sample, scores[0]))

    def _step_plain(self):
        new_population = []
        samples = self.metaheuristic_base.sample_candidates_plain(
            self.population, self.agent_top_individual
        )
        scores = self.score_requester.request_score_plain(samples)
        if self.score_precision is not None:
            for score in scores:
                score.round(self.score_precision)

        candidates = [
            self.individual_type(samples[i].copy(), scores[i])
            for i in range(len(samples))
        ]
        new_population = self.metaheuristic_base.build_updated_population(
            self.population, candidates
        )
        self.population = new_population

    def _step_incremental(self):
        new_population = []
        sample, deltas = self.metaheuristic_base.sample_candidates_incremental(
            self.population, self.agent_top_individual
        )
        scores = self.score_requester.request_score_incremental(sample, deltas)
        if self.score_precision is not None:
            for score in scores:
                score.round(self.score_precision)

        new_population, new_values = (
            self.metaheuristic_base.build_updated_population_incremental(
                self.population, sample, deltas, scores
            )
        )
        if self.score_requester.is_greynet and new_values is not None:
            self.score_requester.cotwin.score_calculator.commit_deltas(new_values)

        self.population = new_population

    def _send_receive_updates(self):
        if self.is_linux:
            self._send_receive_updates_linux()
        else:
            self._send_receive_updates_universal()

    def _send_receive_updates_universal(self):
        if int(self.agent_id) % 2 == 0:
            self._send_updates_universal()
            self._get_updates_universal()
        else:
            self._get_updates_universal()
            self._send_updates_universal()
        self.steps_to_send_updates = self.migration_frequency

    def _migration_request(self):
        migrants_count = max(1, math.ceil(self.migration_rate * len(self.population)))
        migrants = self.individual_type.convert_individuals_to_lists(
            self.population[:migrants_count]
        )
        return {
            "agent_id": self.agent_id,
            "round_robin_status_dict": self.round_robin_status_dict,
            "request_type": "put_updates",
            "migrants": migrants,
        }

    def _send_updates_universal(self):
        self._socket_send(
            self.agent_to_agent_socket_sender, pickle.dumps("ready to send updates")
        )
        self._socket_receive(self.agent_to_agent_socket_sender)
        self._socket_send(
            self.agent_to_agent_socket_sender, pickle.dumps(self._migration_request())
        )
        return pickle.loads(self._socket_receive(self.agent_to_agent_socket_sender))

    def _get_updates_universal(self):
        self._socket_receive(self.agent_to_agent_socket_receiver)
        self._socket_send(
            self.agent_to_agent_socket_receiver, pickle.dumps(str(self.agent_id))
        )
        updates = pickle.loads(
            self._socket_receive(self.agent_to_agent_socket_receiver)
        )
        self._socket_send(
            self.agent_to_agent_socket_receiver,
            pickle.dumps("Successfully received updates"),
        )
        self._apply_migrants(updates)

    def _send_receive_updates_linux(self):
        if int(self.agent_id) % 2 == 0:
            self._send_updates_linux()
            self._get_updates_linux()
        else:
            self._get_updates_linux()
            self._send_updates_linux()
        self.steps_to_send_updates = self.migration_frequency

    def _send_updates_linux(self):
        self._pipe_send(self.agent_to_agent_pipe_sender, self._migration_request())
        return self._pipe_receive(self.agent_to_agent_pipe_sender)

    def _get_updates_linux(self):
        updates = self._pipe_receive(self.agent_to_agent_pipe_receiver)
        self._pipe_send(
            self.agent_to_agent_pipe_receiver, "Successfully received updates"
        )
        self._apply_migrants(updates)

    def _apply_migrants(self, updates):
        migrants = self.individual_type.convert_lists_to_individuals(
            updates["migrants"]
        )
        count = len(migrants)
        if self.metaheuristic_base.metaheuristic_kind == "Population":
            natives = self.population[-count:]
            self.population[-count:] = [
                migrant if migrant.score < native.score else native
                for migrant, native in zip(migrants, natives)
            ]
        elif self.metaheuristic_base.metaheuristic_kind == "LocalSearch":
            natives = self.population[:count]
            self.population[:count] = [
                migrant if migrant.score < native.score else native
                for migrant, native in zip(migrants, natives)
            ]
        else:
            raise ValueError("metaheuristic_kind can be only Population or LocalSearch")
        self.round_robin_status_dict = updates["round_robin_status_dict"]
        self.round_robin_status_dict[self.agent_id] = self.agent_status

    def _send_candidate_to_master(self, step_id):
        self._send_candidate_to_master_universal(step_id)

    def _make_publication(self, step_id, include_metadata=False):
        include_metadata = (
            include_metadata or not self.is_master_received_variables_info
        )
        return {
            "agent_id": self.agent_id,
            "status": self.agent_status,
            "candidate": self.agent_top_individual.as_list(),
            "step": step_id,
            "score_variant": self.score_variant,
            "variable_names": self.score_requester.variables_manager.get_variables_names_vec()
            if include_metadata
            else None,
            "discrete_ids": self.score_requester.variables_manager.discrete_ids
            if include_metadata
            else None,
        }

    def _send_candidate_to_master_universal(self, step_id):
        self._socket_send(
            self.agent_to_master_socket_publisher,
            pickle.dumps(self._make_publication(step_id)),
        )

    def _check_global_updates(self):
        self._check_global_updates_universal()

    def _check_global_updates_universal(self):
        candidate, metadata_received, is_end = pickle.loads(
            self._socket_receive(self.agent_to_master_subscriber_socket)
        )
        self.is_end = is_end
        if is_end:
            return
        self.is_master_received_variables_info |= metadata_received
        if self.is_win_from_comparing_with_global and candidate is not None:
            individual = Individual.get_related_individual_type(
                self.score_variant
            ).from_list(candidate)
            if individual < self.agent_top_individual:
                self.agent_top_individual = individual
                self.population[0] = individual.copy()
