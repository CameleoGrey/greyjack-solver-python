"""Small, spawn-importable fixtures exercising the real Agent lifecycle.

The score requester deliberately avoids dataframe/native bridge dependencies.
Population creation, migration, publications and cancellation still use Agent.
"""

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import multiprocess

from greyjack.agents.base.Agent import Agent
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.score_calculation.scores.SimpleScore import SimpleScore


class FixtureFailure(Exception):
    pass


class FixtureBaseFailure(BaseException):
    pass


def record(directory, worker_id, event, **details):
    with (Path(directory) / f"worker-{worker_id}.jsonl").open("a") as stream:
        stream.write(json.dumps({"event": event, **details}) + "\n")


def read_events(directory, worker_id):
    path = Path(directory) / f"worker-{worker_id}.jsonl"
    if not path.exists():
        return []
    result = []
    for line in path.read_text().splitlines():
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            # Another thread/process may be in the middle of appending a line.
            continue
    return result


def wait_for_event(directory, worker_id, event, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(entry["event"] == event for entry in read_events(directory, worker_id)):
            return
        time.sleep(0.01)
    raise AssertionError(f"Worker {worker_id} did not reach {event}")


class FixtureDomainBuilder:
    def build_domain_from_scratch(self):
        return {"value": 5000}

    def build_from_domain(self, domain):
        return dict(domain)

    def build_from_solution(self, solution, initial_domain=None):
        return {"value": solution.variable_values_dict["x"]}


class FixtureCotwinBuilder:
    def build_cotwin(self, domain, is_already_initialized=False):
        return SimpleNamespace(
            score_calculator=SimpleNamespace(
                score_variant=ScoreVariants.SimpleScore, is_incremental=False
            )
        )


class FixtureVariables:
    discrete_ids = []

    def __init__(self, worker_id):
        self.worker_id = int(worker_id)

    def sample_variables(self):
        return [5000 - 100 * self.worker_id]

    def get_variables_names_vec(self):
        return ["x"]


class FixtureRequester:
    def __init__(self, agent):
        self.agent = agent
        self.variables_manager = FixtureVariables(agent.agent_id)
        self.calls = 0

    def request_score_plain(self, samples):
        self.calls += 1
        initial = self.calls == 1
        record(
            self.agent.directory,
            self.agent.agent_id,
            "initial_score" if initial else "score",
        )
        targeted = self.agent.agent_id == str(self.agent.failing_worker)
        if initial and self.agent.scenario == "stop_before":
            marker = Path(self.agent.directory) / "stop-requested"
            deadline = time.monotonic() + 5
            while not marker.exists():
                if time.monotonic() >= deadline:
                    raise AssertionError(
                        "Initial scoring never received the stop request"
                    )
                time.sleep(0.01)
        if initial and targeted and self.agent.scenario == "initial_failure":
            raise FixtureFailure("initial-score fixture sentinel")
        if initial and targeted and self.agent.scenario == "base_exception":
            raise FixtureBaseFailure("base-exception fixture sentinel")
        if not initial and self.calls == 3 and targeted:
            if self.agent.scenario == "step_failure":
                raise FixtureFailure("later-step fixture sentinel")
            if self.agent.scenario == "nonfirst_failure":
                wait_for_event(self.agent.directory, "0", "step")
                raise FixtureFailure("nonfirst-worker fixture sentinel")
        if (
            self.agent.scenario == "uncooperative_process"
            and self.agent.agent_id == "0"
        ):
            record(self.agent.directory, self.agent.agent_id, "callback_blocked")
            time.sleep(30)
        return [SimpleScore(sample[0]) for sample in samples]


class FixtureMetaheuristic:
    metaheuristic_kind = "LocalSearch"

    def __init__(self, agent):
        self.agent = agent
        self.steps = 0

    def sample_candidates_plain(self, population, best):
        self.steps += 1
        record(self.agent.directory, self.agent.agent_id, "step", step=self.steps)
        time.sleep(0.01)
        return [[5000 - 100 * int(self.agent.agent_id) - self.steps]]

    def build_updated_population(self, population, candidates):
        return candidates


class FixtureTermination:
    def __init__(self, limits):
        self.limits = tuple(limits)
        self.steps = 0
        self.limit = None

    def update(self, agent):
        self.limit = self.limits[int(agent.agent_id)]
        self.steps = agent.metaheuristic_base.steps

    def is_accomplish(self):
        return self.limit is not None and self.steps >= self.limit


class FixtureAgent(Agent):
    def __init__(self, directory, scenario="normal", workers=1, failing_worker=0):
        limits = [1 + 2 * index for index in range(workers)]
        if scenario not in ("normal", "normal_sparse_publications", "reuse_ports"):
            limits = [100000] * workers
        super().__init__(
            migration_rate=1,
            migration_frequency=1,
            termination_strategy=FixtureTermination(limits),
            compare_to_global_frequency=(
                100000 if scenario == "normal_sparse_publications" else 1
            ),
        )
        self.directory = str(directory)
        self.scenario = scenario
        self.failing_worker = failing_worker
        self.population_size = 1
        self.is_win_from_comparing_with_global = True

    def _build_logger(self):
        if self.scenario == "startup_failure" and self.agent_id == str(
            self.failing_worker
        ):
            record(self.directory, self.agent_id, "startup_before_logger")
            assert self.logger is None
            raise FixtureFailure("startup fixture sentinel")
        super()._build_logger()

    def _build_cotwin(self):
        record(
            self.directory,
            self.agent_id,
            "startup",
            start_method=multiprocess.get_start_method(),
        )
        if self.agent_id == str(self.failing_worker):
            if self.scenario == "process_exit":
                wait_for_event(self.directory, "0", "initial_score")
                os._exit(17)
            if self.scenario == "uncooperative_process":
                wait_for_event(self.directory, "0", "callback_blocked")
                raise FixtureFailure("blocked-peer fixture sentinel")
        super()._build_cotwin()

    def _build_metaheuristic_base(self):
        self.score_requester = FixtureRequester(self)
        self.metaheuristic_base = FixtureMetaheuristic(self)

    def _send_receive_updates(self):
        super()._send_receive_updates()
        if self.agent_status != "alive":
            record(self.directory, self.agent_id, "relayed_after_termination")


class StopObserver:
    def __init__(self, solver):
        self.solver = solver
        self.incumbents = []

    def update_solution(self, solution):
        assert solution is not None
        self.incumbents.append(solution)
        self.solver.stop()


class FailingObserver:
    def update_solution(self, solution):
        raise FixtureFailure("coordinator-observer fixture sentinel")
