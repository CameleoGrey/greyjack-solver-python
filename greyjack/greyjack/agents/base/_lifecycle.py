"""Private worker control shared by the process and thread solver backends."""

import pickle
import signal
import traceback
from queue import Empty, Full, Queue


POLL_SECONDS = 0.05
SHUTDOWN_GRACE_SECONDS = 2.0
_process_cancellation = None
_process_events = None
_process_pipes = None


class AgentCancelled(Exception):
    """Internal cooperative stop; it is not a scoring failure."""


def initialize_process_worker(cancellation, events, pipes):
    # These handles are transferred during spawn, not pickled as pool task data.
    global _process_cancellation, _process_events, _process_pipes
    _process_cancellation = cancellation
    _process_events = events
    _process_pipes = pipes
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def run_agent(agent, cancellation=None, events=None):
    process_worker = cancellation is None
    agent._cancellation = _process_cancellation if process_worker else cancellation
    agent._lifecycle_events = _process_events if process_worker else events
    if process_worker and _process_pipes:
        sender, receiver = _process_pipes[int(agent.agent_id)]
        agent.agent_to_agent_pipe_sender = sender
        agent.agent_to_agent_pipe_receiver = receiver
    try:
        agent.solve()
        agent._lifecycle_events.put(
            pickle.dumps({"kind": "returned", "agent_id": agent.agent_id})
        )
    except Exception as error:
        # Ordinary exceptions retain their type and remote traceback in AsyncResult.
        if hasattr(error, "add_note"):
            error.add_note(
                f"Agent {agent.agent_id}, phase {getattr(agent, '_phase', 'startup')}"
            )
        raise
    except BaseException as error:
        # SystemExit and PyO3 panic exceptions otherwise kill a pool worker without
        # completing its result. A built-in exception is safe to transport.
        raise RuntimeError(
            f"Agent {agent.agent_id} failed during "
            f"{getattr(agent, '_phase', 'startup')}: "
            f"{type(error).__name__}: {error}\n{traceback.format_exc()}"
        ) from None


class QueueConnection:
    """A cancellable duplex endpoint for threads, with Pipe-style payload copies."""

    def __init__(self, incoming, outgoing, cancellation):
        self._incoming = incoming
        self._outgoing = outgoing
        self._cancellation = cancellation
        self._pending = None
        self._closed = False

    def _check(self):
        if self._cancellation.is_set():
            raise AgentCancelled()
        if self._closed:
            raise OSError("Migration connection is closed")

    def send(self, value):
        payload = pickle.dumps(value)
        while True:
            self._check()
            try:
                self._outgoing.put(payload, timeout=POLL_SECONDS)
                return
            except Full:
                pass

    def poll(self, timeout=0.0):
        self._check()
        if self._pending is not None:
            return True
        try:
            self._pending = self._incoming.get(timeout=timeout)
            return True
        except Empty:
            return False

    def recv(self):
        while not self.poll(POLL_SECONDS):
            pass
        payload, self._pending = self._pending, None
        return pickle.loads(payload)

    def close(self):
        self._closed = True


def queue_pipe(cancellation):
    first, second = Queue(maxsize=1), Queue(maxsize=1)
    return (
        QueueConnection(first, second, cancellation),
        QueueConnection(second, first, cancellation),
    )
