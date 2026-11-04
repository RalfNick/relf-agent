"""Local test host lifetime, separate from Agent execution and child deadlines."""

import os
import subprocess

import pytest


def module():
    from . import host_awake

    return host_awake


class Process:
    def __init__(self, *, exited=None, slow_termination=False):
        self.returncode = exited
        self.slow_termination = slow_termination
        self.events = []

    def poll(self):
        return self.returncode

    def terminate(self):
        self.events.append("terminate")

    def kill(self):
        self.events.append("kill")
        self.returncode = -9

    def wait(self, timeout):
        self.events.append(("wait", timeout))
        if self.slow_termination:
            self.slow_termination = False
            raise subprocess.TimeoutExpired("owned-caffeinate", timeout)
        if self.returncode is None:
            self.returncode = -15
        return self.returncode


def configure(monkeypatch, process):
    m = module()
    monkeypatch.setattr(m.sys, "platform", "darwin")
    launches = []

    def spawn(args, **kwargs):
        launches.append((args, kwargs))
        return process

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    return m, launches


def test_non_darwin_has_no_local_power_process(monkeypatch):
    m = module()
    monkeypatch.setattr(m.sys, "platform", "linux")
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("unexpected process"))
    with m.keep_awake():
        pass


def test_guard_owns_only_its_original_process_through_context(monkeypatch):
    process = Process()
    m, launches = configure(monkeypatch, process)
    with m.keep_awake() as guard:
        assert guard is process
        assert process.events == [] and process.returncode is None
        args, options = launches[0]
        assert args == ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())]
        assert options["start_new_session"] is True and options["close_fds"] is True
        assert options["stdout"] == options["stderr"] == subprocess.DEVNULL
    assert process.events == ["terminate", ("wait", 5)]
    assert len(launches) == 1 and process.returncode == -15


def test_interrupt_still_reaps_the_original_guard(monkeypatch):
    process = Process()
    m, _ = configure(monkeypatch, process)
    with pytest.raises(KeyboardInterrupt), m.keep_awake():
        raise KeyboardInterrupt
    assert process.events == ["terminate", ("wait", 5)] and process.returncode == -15


@pytest.mark.parametrize("when", ["startup", "during_round"])
def test_lost_guard_cannot_confirm_a_protected_round(monkeypatch, when):
    process = Process(exited=0 if when == "startup" else None)
    m, _ = configure(monkeypatch, process)
    entered = False
    with pytest.raises(RuntimeError, match="awake"):
        with m.keep_awake():
            entered = True
            process.returncode = 0
    assert entered == (when == "during_round")
    assert process.events == [("wait", 5)]


def test_stubborn_guard_is_killed_and_reaped_without_unbounded_wait(monkeypatch):
    process = Process(slow_termination=True)
    m, _ = configure(monkeypatch, process)
    with m.keep_awake():
        pass
    assert process.events == ["terminate", ("wait", 5), "kill", ("wait", 5)]
    assert process.returncode == -9
