"""Subprocess entry point: keep failure/interrupt regressions bounded and isolated."""

import argparse
import json
import multiprocessing
import pickle
import socket
import threading
import time
from pathlib import Path

import zmq

from greyjack.SolverOOP import SolverOOP
from greyjack.agents.base.LoggingLevel import LoggingLevel
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend

from lifecycle_fixtures import (
    FailingObserver,
    FixtureAgent,
    FixtureCotwinBuilder,
    FixtureDomainBuilder,
    FixtureFailure,
    StopObserver,
    read_events,
    wait_for_event,
)


def free_ports(count):
    sockets = []
    try:
        for _ in range(count):
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [str(sock.getsockname()[1]) for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def assert_ports_released(ports):
    for port in ports:
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", int(port)))


def assert_workers_released(initial_threads):
    deadline = time.monotonic() + 2
    while True:
        children = multiprocessing.active_children()
        try:
            import multiprocess
        except ImportError:
            pass
        else:
            children += multiprocess.active_children()
        threads = [
            thread
            for thread in threading.enumerate()
            if thread.ident not in initial_threads and thread.is_alive()
        ]
        if not children and not threads:
            return
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"Workers leaked: children={[child.pid for child in children]}, "
                f"threads={[thread.name for thread in threads]}"
            )
        time.sleep(0.01)


def check_communication(directory):
    from greyjack.agents.base._lifecycle import AgentCancelled, queue_pipe

    cancellation = threading.Event()
    first, second = queue_pipe(cancellation)
    try:
        payload = {"values": [1, 2]}
        first.send(payload)
        payload["values"].append(3)
        assert second.poll(0.1)
        assert second.recv() == {"values": [1, 2]}
    finally:
        first.close()
        second.close()

    for operation in ("send", "recv"):
        cancellation = threading.Event()
        first, second = queue_pipe(cancellation)
        entered = threading.Event()
        errors = []
        if operation == "send":
            first.send("occupy the bounded migration queue")

        def blocked_operation():
            entered.set()
            try:
                if operation == "send":
                    first.send("cannot fit until cancelled")
                else:
                    second.recv()
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=blocked_operation)
        thread.start()
        try:
            assert entered.wait(1)
            thread.join(timeout=0.1)
            assert thread.is_alive(), f"{operation} did not block"
            cancellation.set()
            thread.join(timeout=2)
            assert not thread.is_alive(), f"{operation} ignored cancellation"
            assert len(errors) == 1 and isinstance(errors[0], AgentCancelled), errors
        finally:
            cancellation.set()
            thread.join(timeout=2)
            first.close()
            second.close()

    for transport in ("socket", "pipe"):
        cancellation = threading.Event()
        entered = threading.Event()
        errors = []

        def wait_without_peer():
            agent = FixtureAgent(directory)
            agent._cancellation = cancellation
            context = None
            connections = []
            try:
                if transport == "socket":
                    context = zmq.Context()
                    receiver = context.socket(zmq.PAIR)
                    receiver.bind("inproc://lifecycle-cancelled-receive")
                    connections.append(receiver)
                    entered.set()
                    agent._socket_receive(receiver)
                else:
                    receiver, sender = multiprocessing.Pipe()
                    connections.extend((receiver, sender))
                    entered.set()
                    agent._pipe_receive(receiver)
            except BaseException as error:
                errors.append(error)
            finally:
                for connection in connections:
                    connection.close()
                if context is not None:
                    context.term()

        thread = threading.Thread(target=wait_without_peer)
        thread.start()
        try:
            assert entered.wait(1)
            thread.join(timeout=0.1)
            assert thread.is_alive(), f"{transport} receive did not wait for its peer"
            cancellation.set()
            thread.join(timeout=2)
            assert not thread.is_alive(), f"{transport} receive ignored cancellation"
            assert len(errors) == 1 and isinstance(errors[0], AgentCancelled), errors
        finally:
            cancellation.set()
            thread.join(timeout=2)

    context = zmq.Context()
    receiver, sender = context.socket(zmq.PAIR), context.socket(zmq.PAIR)
    try:
        receiver.bind("inproc://lifecycle-terminal-none")
        sender.connect("inproc://lifecycle-terminal-none")
        agent = FixtureAgent(directory)
        agent._cancellation = threading.Event()
        agent.agent_to_master_subscriber_socket = receiver
        sender.send(pickle.dumps([None, False, True]))
        agent._check_global_updates_universal()
        assert agent.is_end is True
        assert agent.agent_top_individual is None
    finally:
        receiver.close(linger=0)
        sender.close(linger=0)
        context.term()


def solve_again_on_same_ports(args, backend, ports, initial_threads):
    repeated_directory = args.directory / "repeated"
    repeated_directory.mkdir()
    repeated = SolverOOP(
        FixtureDomainBuilder(),
        FixtureCotwinBuilder(),
        FixtureAgent(repeated_directory, workers=args.workers),
        parallelization_backend=backend,
        logging_level=LoggingLevel.Warn,
        n_jobs=args.workers,
        available_ports=ports,
    ).solve()
    assert repeated is not None
    assert_workers_released(initial_threads)
    assert_ports_released(ports)
    return repeated


def run(args):
    if args.scenario == "communication":
        initial_threads = {thread.ident for thread in threading.enumerate()}
        check_communication(args.directory)
        assert_workers_released(initial_threads)
        print(json.dumps({"scenario": "communication", "cleaned_up": True}), flush=True)
        return
    backend = (
        ParallelizationBackend.Threading
        if args.backend == "thread"
        else ParallelizationBackend.Multiprocessing
    )
    ports = free_ports(args.workers + 2)
    initial_threads = {thread.ident for thread in threading.enumerate()}
    solver = SolverOOP(
        FixtureDomainBuilder(),
        FixtureCotwinBuilder(),
        FixtureAgent(args.directory, args.scenario, args.workers, args.failing_worker),
        parallelization_backend=backend,
        logging_level=LoggingLevel.Warn,
        n_jobs=args.workers,
        available_ports=ports,
    )
    helper = None
    helper_errors = []
    stopped_without_incumbent = []
    observer = None
    if args.scenario == "stop_after":
        observer = StopObserver(solver)
        solver.register_observer(observer)
    elif args.scenario == "observer_failure":
        solver.register_observer(FailingObserver())
    if args.scenario in ("stop_before", "interrupt"):

        def request_control():
            try:
                event = "initial_score" if args.scenario == "stop_before" else "step"
                wait_for_event(args.directory, "0", event)
                if args.scenario == "stop_before":
                    stopped_without_incumbent.append(solver.global_top_solution is None)
                    solver.stop()
                    (args.directory / "stop-requested").touch()
                else:
                    print("READY_FOR_INTERRUPT", flush=True)
            except BaseException as error:
                helper_errors.append(error)

        helper = threading.Thread(target=request_control)
        helper.start()
    began = time.monotonic()
    error = None
    result = None
    reserved_port = None
    if args.scenario == "partial_bind_failure":
        reserved_port = socket.socket()
        reserved_port.bind(("127.0.0.1", int(ports[1])))
        reserved_port.listen(1)
    try:
        result = solver.solve()
    except BaseException as caught:
        error = caught
    finally:
        if reserved_port is not None:
            reserved_port.close()
    elapsed = time.monotonic() - began
    if helper is not None:
        helper.join(timeout=6)
        assert not helper.is_alive(), "Control helper was not released"
    assert not helper_errors, helper_errors
    assert solver.is_running is False
    assert_workers_released(initial_threads)
    assert_ports_released(ports)

    failure_markers = {
        "startup_failure": "startup fixture sentinel",
        "initial_failure": "initial-score fixture sentinel",
        "step_failure": "later-step fixture sentinel",
        "nonfirst_failure": "nonfirst-worker fixture sentinel",
        "base_exception": "base-exception fixture sentinel",
        "uncooperative_process": "blocked-peer fixture sentinel",
    }
    if args.scenario in failure_markers:
        assert isinstance(error, RuntimeError), repr(error)
        message = str(error)
        assert failure_markers[args.scenario] in message, message
        assert "agent" in message.lower(), message
        assert str(args.failing_worker) in message, message
        if args.scenario != "base_exception":
            assert isinstance(error.__cause__, FixtureFailure), repr(error.__cause__)
        if args.scenario == "nonfirst_failure":
            assert any(
                entry["event"] == "step" for entry in read_events(args.directory, "0")
            )
    elif args.scenario == "process_exit":
        assert isinstance(error, RuntimeError), repr(error)
        assert "17" in str(error), str(error)
    elif args.scenario == "interrupt":
        assert isinstance(error, KeyboardInterrupt), repr(error)
    elif args.scenario == "observer_failure":
        assert isinstance(error, FixtureFailure), repr(error)
        assert "coordinator-observer fixture sentinel" in str(error)
        assert error.__cause__ is None
    elif args.scenario == "partial_bind_failure":
        assert isinstance(error, zmq.ZMQError), repr(error)
        assert error.errno == zmq.EADDRINUSE, repr(error)
        solve_again_on_same_ports(args, backend, ports, initial_threads)
    else:
        assert error is None, repr(error)
        if args.scenario == "stop_before":
            assert stopped_without_incumbent == [True]
            assert result is None, result
        elif args.scenario == "stop_after":
            assert observer.incumbents
            assert result is not None
            assert result.score <= observer.incumbents[0].score
            assert result.variable_values_dict["x"] == result.score[0]
        else:
            assert result is not None
            for worker in range(args.workers):
                completed = [
                    event["step"]
                    for event in read_events(args.directory, str(worker))
                    if event["event"] == "step"
                ]
                assert completed == list(range(1, 2 + 2 * worker)), completed
            if args.workers > 1:
                assert any(
                    event["event"] == "relayed_after_termination"
                    for event in read_events(args.directory, "0")
                ), "The earliest finished worker did not relay migration updates"
            expected = 5000 - 100 * (args.workers - 1) - (1 + 2 * (args.workers - 1))
            assert result.variable_values_dict == {"x": float(expected)}
            assert result.score == [float(expected)]
            if args.backend == "process":
                for worker in range(args.workers):
                    startup = next(
                        event
                        for event in read_events(args.directory, str(worker))
                        if event["event"] == "startup"
                    )
                    assert startup["start_method"] == "spawn", startup
            if args.scenario == "reuse_ports":
                repeated = solve_again_on_same_ports(
                    args, backend, ports, initial_threads
                )
                assert repeated.score == result.score
                assert repeated.variable_values_dict == result.variable_values_dict
    print(
        json.dumps(
            {
                "scenario": args.scenario,
                "backend": args.backend,
                "workers": args.workers,
                "elapsed": elapsed,
                "error": None if error is None else str(error),
                "cleaned_up": True,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("backend", choices=("thread", "process"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--failing-worker", type=int, default=0)
    run(parser.parse_args())
