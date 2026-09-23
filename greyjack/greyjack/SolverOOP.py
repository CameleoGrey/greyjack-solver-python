"""Parallel OO solver with supervised workers and cooperative shutdown."""

import logging
import pickle
import sys
import threading
import time
import uuid
from copy import deepcopy
from queue import Empty, Queue

import multiprocess
import zmq
from pathos.multiprocessing import ProcessPool
from pathos.threading import ThreadPool

from greyjack.agents.base.GJSolution import GJSolution
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents.base._lifecycle import (
    POLL_SECONDS,
    SHUTDOWN_GRACE_SECONDS,
    initialize_process_worker,
    queue_pipe,
    run_agent,
)
from greyjack.agents.base.individuals.Individual import Individual


class SolverOOP:
    def __init__(
        self,
        domain_builder,
        cotwin_builder,
        agent,
        parallelization_backend=ParallelizationBackend.Multiprocessing,
        logging_level=LoggingLevel.Info,
        n_jobs=None,
        score_precision=None,
        available_ports=None,
        default_port="25000",
        initial_solution=None,
    ):
        """Linux uses two localhost ports; other platforms use n_jobs + two."""
        self.domain_builder = domain_builder
        self.cotwin_builder = cotwin_builder
        self.agent = agent
        self.n_jobs = (
            max(1, multiprocess.cpu_count() // 2) if n_jobs is None else n_jobs
        )
        if type(self.n_jobs) is not int or self.n_jobs < 1:
            raise ValueError("n_jobs must be a positive integer")
        self.score_precision = score_precision
        self.logging_level = logging_level
        self.parallelization_backend = parallelization_backend
        self.available_ports = available_ports
        self.default_port = default_port
        self.initial_solution = initial_solution
        self.is_agent_wins_from_comparing_with_global = (
            agent.is_win_from_comparing_with_global
        )
        self.is_linux = "linux" in sys.platform
        self.observers = []
        self.is_running = False
        self._solve_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._cancellation = None
        self._events = None
        self._pool = None
        self._jobs = {}
        self._workers = []
        self._pipes = []
        self._process_pipes = []
        self.context = None
        self.master_to_agents_subscriber_socket = None
        self.master_to_agents_publisher_socket = None
        self._logger_handler = None
        self._logger_name = f"greyjack.solver.{uuid.uuid4().hex}"
        self._reset_results()
        self._build_logger()

    def _reset_results(self):
        self.global_top_individual = None
        self.global_top_solution = None
        self.variable_names = None
        self.discrete_ids = None
        self.is_variables_info_received = False
        self.agent_statuses = {}
        self._finished_agents = set()
        self._checked_jobs = set()

    def _build_logger(self):
        if self.logging_level is None:
            self.logging_level = LoggingLevel.Info
        if self.logging_level not in (
            LoggingLevel.FreshOnly,
            LoggingLevel.Info,
            LoggingLevel.Warn,
        ):
            raise ValueError("logging_level must be a LoggingLevel value")
        self.logger = logging.getLogger(self._logger_name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if self._logger_handler is None:
            self._logger_handler = logging.StreamHandler()
            self._logger_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s, %(levelname)s: %(message)s",
                    datefmt="%Y/%m/%d %H:%M:%S",
                )
            )
            self.logger.addHandler(self._logger_handler)

    def _init_master_pub_sub(self):
        required = 2 if self.is_linux else self.n_jobs + 2
        if self.available_ports is None:
            self.available_ports = [
                str(int(self.default_port) + i) for i in range(required)
            ]
        if len(self.available_ports) < required:
            raise ValueError(f"At least {required} available ports are required")
        self.address = "localhost"
        self.master_subscriber_address = (
            f"tcp://{self.address}:{self.available_ports[0]}"
        )
        self.master_publisher_address = (
            f"tcp://{self.address}:{self.available_ports[1]}"
        )
        self.context = zmq.Context()
        self.master_to_agents_subscriber_socket = self.context.socket(zmq.SUB)
        self.master_to_agents_subscriber_socket.setsockopt(zmq.LINGER, 0)
        self.master_to_agents_subscriber_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.master_to_agents_subscriber_socket.setsockopt(zmq.CONFLATE, 1)
        self.master_to_agents_subscriber_socket.bind(self.master_subscriber_address)
        self.master_to_agents_publisher_socket = self.context.socket(zmq.PUB)
        self.master_to_agents_publisher_socket.setsockopt(zmq.LINGER, 0)
        self.master_to_agents_publisher_socket.bind(self.master_publisher_address)
        if not self.is_linux:
            self.available_agent_to_agent_ports = self.available_ports[2:required]

    def stop(self):
        """Request cancellation; the solve thread owns all socket operations."""
        if self.is_running:
            self._stop_requested.set()
            cancellation = self._cancellation
            if cancellation is not None:
                cancellation.set()

    def solve(self):
        if not self._solve_lock.acquire(blocking=False):
            raise RuntimeError("This solver is already running")
        self._stop_requested.clear()
        self.is_running = True
        self._reset_results()
        self._started_at = time.perf_counter()
        try:
            self._build_logger()
            if self.parallelization_backend == ParallelizationBackend.Multiprocessing:
                self._process_context = multiprocess.get_context("spawn")
                self._cancellation = self._process_context.Event()
                # Synchronous writes preserve final data without a feeder thread
                # or closing a process-global queue after each agent task.
                self._events = self._process_context.SimpleQueue()
            elif self.parallelization_backend == ParallelizationBackend.Threading:
                self._cancellation = threading.Event()
                self._events = Queue()
            else:
                raise ValueError(
                    "parallelization_backend must be a ParallelizationBackend value"
                )
            if self._stop_requested.is_set():
                self._cancellation.set()
            self._init_master_pub_sub()
            agents = self._setup_agents()
            if not self._cancellation.is_set():
                self._run_jobs(agents)
            while not self._cancellation.is_set():
                # Supervision is independent of score publications, including startup.
                self._check_jobs()
                self._drain_events()
                if len(self._finished_agents) == self.n_jobs:
                    self._cancellation.set()
                    break
                if self.master_to_agents_subscriber_socket.poll(
                    int(POLL_SECONDS * 1000)
                ):
                    publication = pickle.loads(
                        self.master_to_agents_subscriber_socket.recv()
                    )
                    self._accept_publication(publication)
                # Retry the latest state even if an early PUB reply was dropped.
                self.send_global_update(is_end=False)
        finally:
            original_error = sys.exc_info()[1]
            try:
                self._shutdown()
            except BaseException:
                if original_error is None:
                    raise
                self.logger.warning("Cleanup also failed", exc_info=True)
            finally:
                self.is_running = False
                self._solve_lock.release()
        return self.global_top_solution

    def _run_jobs(self, agents):
        pool_name = str(uuid.uuid4())
        if self.parallelization_backend == ParallelizationBackend.Threading:
            self._pool = ThreadPool(nodes=self.n_jobs, id=pool_name)
        else:
            self._pool = ProcessPool(
                nodes=self.n_jobs,
                id=pool_name,
                context=self._process_context,
                initializer=initialize_process_worker,
                initargs=(self._cancellation, self._events, self._process_pipes),
            )
            # Keep original Process objects: a pool may silently replace a crashed
            # native worker while its submitted job remains permanently unfinished.
            self._workers = list(self._pool._serve()._pool)
        for agent in agents:
            if self.parallelization_backend == ParallelizationBackend.Threading:
                job = self._pool.apipe(
                    run_agent, agent, self._cancellation, self._events
                )
            else:
                job = self._pool.apipe(run_agent, agent)
            self._jobs[agent.agent_id] = job
        return self._pool

    def _check_jobs(self, check_health=True):
        for agent_id, job in self._jobs.items():
            if agent_id not in self._checked_jobs and job.ready():
                self._checked_jobs.add(agent_id)
                try:
                    job.get(timeout=0)
                except Exception as error:
                    raise RuntimeError(f"Agent {agent_id} failed: {error}") from error
        if check_health:
            for worker in self._workers:
                if worker.exitcode is not None:
                    raise RuntimeError(
                        f"Solver worker PID {worker.pid} exited unexpectedly "
                        f"with exit code {worker.exitcode}"
                    )

    def _setup_agents(self):
        agents = [deepcopy(self.agent) for _ in range(self.n_jobs)]
        for i, agent in enumerate(agents):
            agent.agent_id = str(i)
            agent.domain_builder = deepcopy(self.domain_builder)
            agent.cotwin_builder = deepcopy(self.cotwin_builder)
            agent.initial_solution = deepcopy(self.initial_solution)
            agent.score_precision = deepcopy(self.score_precision)
            agent.logging_level = self.logging_level
            agent.total_agents_count = self.n_jobs
            agent.master_subscriber_address = self.master_subscriber_address
            agent.master_publisher_address = self.master_publisher_address
            self.agent_statuses[str(i)] = "alive"
            agent.round_robin_status_dict = {
                str(j): "alive" for j in range(self.n_jobs)
            }
        if self.is_linux:
            senders, receivers = [], []
            for _ in agents:
                if self.parallelization_backend == ParallelizationBackend.Threading:
                    sender, receiver = queue_pipe(self._cancellation)
                else:
                    sender, receiver = self._process_context.Pipe()
                self._pipes.extend((sender, receiver))
                senders.append(sender)
                receivers.append(receiver)
            receivers.append(receivers.pop(0))
            for agent, sender, receiver in zip(agents, senders, receivers):
                if self.parallelization_backend == ParallelizationBackend.Threading:
                    agent.agent_to_agent_pipe_sender = sender
                    agent.agent_to_agent_pipe_receiver = receiver
                else:
                    # Transfer through spawn, not task serialization, avoiding a
                    # persistent global resource-sharer thread for file descriptors.
                    self._process_pipes.append((sender, receiver))
        else:
            for i, agent in enumerate(agents):
                agent.agent_address_for_other_agents = (
                    f"tcp://localhost:{self.available_agent_to_agent_ports[i]}"
                )
            for i, agent in enumerate(agents):
                agent.next_agent_address = agents[
                    (i + 1) % self.n_jobs
                ].agent_address_for_other_agents
        return agents

    def _drain_events(self, notify=True):
        if self._events is None:
            return
        while True:
            try:
                if hasattr(self._events, "get_nowait"):
                    payload = self._events.get_nowait()
                else:
                    if not self._events._reader.poll():
                        return
                    payload = self._events.get()
                event = pickle.loads(payload)
            except Empty:
                return
            if event["kind"] in ("finished", "returned"):
                self._finished_agents.add(event["agent_id"])
                self.agent_statuses[event["agent_id"]] = "dead"
            if event.get("publication") is not None:
                self._accept_publication(event["publication"], notify=notify)

    def _decode_publication(self, publication):
        if publication.get("variable_names") is not None:
            self.variable_names = publication["variable_names"]
            self.discrete_ids = publication["discrete_ids"]
            self.is_variables_info_received = True
        individual = Individual.get_related_individual_type_by_value(
            publication["score_variant"]
        ).from_list(publication["candidate"])
        return (
            individual,
            publication["agent_id"],
            publication["status"],
            publication["step"],
        )

    def receive_agent_publication(self):
        return self._decode_publication(
            pickle.loads(self.master_to_agents_subscriber_socket.recv())
        )

    def _accept_publication(self, publication, notify=True):
        individual, agent_id, status, step = self._decode_publication(publication)
        improved = (
            self.global_top_individual is None
            or individual < self.global_top_individual
        )
        if improved:
            self.global_top_individual = individual
            self.update_global_top_solution()
            if notify and self.logging_level == LoggingLevel.FreshOnly:
                self.logger.info(
                    "Agent: %4s Step %s Best score: %s, Solving time: %.6f New best score!",
                    agent_id,
                    step,
                    individual.score,
                    time.perf_counter() - self._started_at,
                )
        # Conflated score messages must never undo reliable final state.
        if agent_id not in self._finished_agents:
            self.agent_statuses[agent_id] = status
        if notify and self.observers:
            self._notify_observers()

    def send_global_update(self, is_end):
        if self.master_to_agents_publisher_socket is None:
            return
        candidate = None
        if (
            self.is_agent_wins_from_comparing_with_global
            and self.global_top_individual is not None
        ):
            candidate = self.global_top_individual.as_list()
        try:
            self.master_to_agents_publisher_socket.send(
                pickle.dumps([candidate, self.is_variables_info_received, is_end]),
                flags=zmq.NOBLOCK,
            )
        except zmq.Again:
            pass

    def _shutdown(self):
        """Drain reliable final data while workers leave cancellable waits."""
        cleanup_error = None
        forced = False
        if self._cancellation is not None:
            self._cancellation.set()
        deadline = time.monotonic() + SHUTDOWN_GRACE_SECONDS
        try:
            if self._pool is not None:
                while True:
                    self.send_global_update(is_end=True)
                    self._drain_events(notify=False)
                    try:
                        self._check_jobs(check_health=False)
                    except Exception as error:
                        if cleanup_error is None:
                            cleanup_error = error
                    if all(job.ready() for job in self._jobs.values()):
                        break
                    if (
                        self.parallelization_backend
                        == ParallelizationBackend.Multiprocessing
                        and time.monotonic() >= deadline
                    ):
                        forced = True
                        self._pool.terminate()
                        break
                    # Threads cannot safely interrupt arbitrary user/native code.
                    # Owned communication waits all check cancellation promptly.
                    time.sleep(POLL_SECONDS)
                if not forced:
                    self._drain_events(notify=False)
                    self._pool.close()
                self._pool.join()
                self._pool.clear()
        finally:
            self._pool = None
            self._jobs = {}
            self._workers = []
            for pipe in self._pipes:
                pipe.close()
            self._pipes = []
            self._process_pipes = []
            for name in (
                "master_to_agents_subscriber_socket",
                "master_to_agents_publisher_socket",
            ):
                socket = getattr(self, name)
                if socket is not None:
                    socket.close(linger=0)
                    setattr(self, name, None)
            if self.context is not None:
                self.context.term()
                self.context = None
            if self._events is not None and hasattr(self._events, "close"):
                self._events.close()
            self._events = None
            self._cancellation = None
            if self._logger_handler is not None:
                self.logger.removeHandler(self._logger_handler)
                self._logger_handler.close()
                self._logger_handler = None
        if cleanup_error is not None:
            raise cleanup_error

    def update_global_top_solution(self):
        if self.global_top_individual is not None and self.variable_names is not None:
            values, score = self.global_top_individual.as_list()
            self.global_top_solution = GJSolution(
                self.variable_names,
                self.discrete_ids,
                values,
                score,
                self.score_precision,
            )

    def register_observer(self, observer):
        self.observers.append(observer)

    def _notify_observers(self):
        for observer in self.observers:
            observer.update_solution(self.global_top_solution)
