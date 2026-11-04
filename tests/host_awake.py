"""Bound a local Mac idle-sleep assertion to this pytest session."""

import os
import subprocess
import sys
from contextlib import contextmanager


def _stop(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@contextmanager
def keep_awake():
    if sys.platform != "darwin":
        yield None
        return
    process = subprocess.Popen(
        ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    try:
        if process.poll() is not None:
            raise RuntimeError("Test host awake guard exited before the session started")
        yield process
        if process.poll() is not None:
            raise RuntimeError("Test host awake guard ended during the session")
    finally:
        _stop(process)
