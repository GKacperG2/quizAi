from uuid import uuid4
import subprocess
import sys
from quiz_assistant.single_instance import SingleInstanceGuard, InstanceResult


def test_second_instance_activates_first_and_cannot_remove_owner(qt_app):
    name = f"quiz-assistant-test-{uuid4()}"
    first, second, third = [SingleInstanceGuard(name) for _ in range(3)]
    activations = []
    first.activation_requested.connect(lambda: activations.append(True))
    try:
        assert first.acquire() is InstanceResult.STARTED
        assert second.acquire() is InstanceResult.ALREADY_RUNNING
        qt_app.processEvents()
        assert activations
        second.close()
        assert third.acquire() is InstanceResult.ALREADY_RUNNING
    finally:
        third.close()
        second.close()
        first.close()


def test_restart_after_close():
    name = f"quiz-assistant-test-{uuid4()}"
    first, second = SingleInstanceGuard(name), SingleInstanceGuard(name)
    assert first.acquire() is InstanceResult.STARTED
    first.close()
    assert second.acquire() is InstanceResult.STARTED
    second.close()


def test_listen_failure_is_distinct_and_recoverable(monkeypatch):
    guard = SingleInstanceGuard(f"quiz-assistant-test-{uuid4()}")
    monkeypatch.setattr(guard._server, "listen", lambda name: False)
    assert guard.acquire() is InstanceResult.ERROR
    assert guard.error
    guard.close()


def test_lock_failure_is_not_already_running(monkeypatch):
    guard = SingleInstanceGuard(f"quiz-assistant-test-{uuid4()}")
    monkeypatch.setattr(guard._lock, "tryLock", lambda ms: False)
    assert guard.acquire() is InstanceResult.ERROR
    assert guard.error
    guard.close()


def test_process_crash_releases_instance_for_restart():
    name = f"quiz-assistant-crash-test-{uuid4()}"
    code = (
        "import sys, os; from PySide6.QtCore import QCoreApplication; "
        "from quiz_assistant.single_instance import SingleInstanceGuard; "
        f"app=QCoreApplication([]); guard=SingleInstanceGuard({name!r}); "
        "print(guard.acquire().name, flush=True); sys.stdin.readline(); os._exit(17)"
    )
    child = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "STARTED"
        # Exit the owning interpreter, not the Windows venv redirector process.
        # os._exit bypasses Qt/Python cleanup, simulating a crash.
        child.stdin.write("crash\n")
        child.stdin.flush()
        child.wait(timeout=5)
        guard = SingleInstanceGuard(name)
        try:
            assert guard.acquire() is InstanceResult.STARTED
        finally:
            guard.close()
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        child.communicate(timeout=5)
