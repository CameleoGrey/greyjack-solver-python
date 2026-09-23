"""Public SolverOOP failure, cancellation, and resource cleanup regressions."""

import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


DRIVER = Path(__file__).with_name("lifecycle_driver.py")


def run_case(tmp_path, scenario, backend, workers=1, failing_worker=0, interrupt=False):
    command = [
        sys.executable,
        str(DRIVER),
        scenario,
        backend,
        str(tmp_path),
        "--workers",
        str(workers),
        "--failing-worker",
        str(failing_worker),
    ]
    process = subprocess.Popen(
        command,
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=os.name == "posix",
    )
    prefix = ""
    try:
        if interrupt:
            deadline = time.monotonic() + 10
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while "READY_FOR_INTERRUPT" not in prefix:
                    remaining = deadline - time.monotonic()
                    assert remaining > 0, "Worker did not become ready for interruption"
                    assert selector.select(timeout=remaining), (
                        "Worker did not become ready for interruption"
                    )
                    line = process.stdout.readline()
                    assert line, "Driver exited before interruption"
                    prefix += line
            process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=20)
    except BaseException:
        # Only this test's new process group is signalled, including its workers.
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.communicate(timeout=5)
        raise
    stdout = prefix + stdout
    assert process.returncode == 0, f"{command}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    report = json.loads(stdout.splitlines()[-1])
    assert report["cleaned_up"] is True
    return report


@pytest.mark.parametrize("backend", ["thread", "process"])
@pytest.mark.parametrize("workers", [1, 2, 3])
def test_normal_completion_and_unequal_worker_lifetimes(tmp_path, backend, workers):
    run_case(tmp_path, "normal", backend, workers=workers)


@pytest.mark.parametrize("backend", ["thread", "process"])
def test_final_solution_is_reliable_without_periodic_score_publications(
    tmp_path, backend
):
    run_case(tmp_path, "normal_sparse_publications", backend, workers=3)


@pytest.mark.parametrize("backend", ["thread", "process"])
def test_next_solver_can_reuse_the_same_ports(tmp_path, backend):
    run_case(tmp_path, "reuse_ports", backend, workers=2)


@pytest.mark.parametrize("backend", ["thread", "process"])
@pytest.mark.parametrize(
    "scenario", ["startup_failure", "initial_failure", "step_failure", "base_exception"]
)
def test_worker_failures_reach_caller_and_release_resources(
    tmp_path, backend, scenario
):
    run_case(tmp_path, scenario, backend)


@pytest.mark.parametrize("backend", ["thread", "process"])
def test_failure_in_nonfirst_worker_is_observed_while_first_worker_is_alive(
    tmp_path, backend
):
    run_case(tmp_path, "nonfirst_failure", backend, workers=2, failing_worker=1)


@pytest.mark.parametrize("backend", ["thread", "process"])
@pytest.mark.parametrize("scenario", ["stop_before", "stop_after"])
def test_explicit_stop_preserves_only_an_available_incumbent(
    tmp_path, backend, scenario
):
    run_case(tmp_path, scenario, backend)


def test_unexpected_worker_process_exit_is_detected(tmp_path):
    run_case(tmp_path, "process_exit", "process", workers=2, failing_worker=1)


def test_failing_worker_does_not_wait_for_uncooperative_process_callback(tmp_path):
    run_case(tmp_path, "uncooperative_process", "process", workers=2, failing_worker=1)


def test_owned_communication_waits_cancel_and_terminal_none_is_safe(tmp_path):
    run_case(tmp_path, "communication", "thread")


@pytest.mark.parametrize("backend", ["thread", "process"])
def test_coordinator_observer_failure_preserves_exception_and_cleans_up(
    tmp_path, backend
):
    run_case(tmp_path, "observer_failure", backend, workers=2)


@pytest.mark.parametrize("backend", ["thread", "process"])
def test_second_bind_failure_releases_first_port_and_allows_reuse(tmp_path, backend):
    run_case(tmp_path, "partial_bind_failure", backend)


@pytest.mark.skipif(os.name != "posix", reason="SIGINT subprocess test requires POSIX")
@pytest.mark.parametrize("backend", ["thread", "process"])
def test_keyboard_interrupt_cleans_workers_and_releases_ports(tmp_path, backend):
    run_case(tmp_path, "interrupt", backend, workers=2, interrupt=True)
