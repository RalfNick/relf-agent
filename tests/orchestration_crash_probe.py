"""Child-only phase evidence; the caller retains the original ten-second gate."""

import atexit
import faulthandler
import json
import os
import time
from pathlib import Path


class CrashProbe:
    def __init__(self):
        self._started = time.monotonic()
        path = os.environ.get("RELF_TEST_CRASH_TRACE")
        self._trace = None if path is None else Path(path).open("x", encoding="utf-8", buffering=1)
        if self._trace is not None:
            self.mark("bootstrap")
            # Capture the stack before the parent's unchanged timeout kills us.
            # This timer records evidence; it never extends or cancels execution.
            faulthandler.dump_traceback_later(8, file=self._trace)
            atexit.register(self.close)

    def mark(self, phase, **fields):
        if self._trace is None or self._trace.closed:
            return
        self._trace.write(
            json.dumps(
                {
                    **fields,
                    "phase": phase,
                    "elapsed": time.monotonic() - self._started,
                    "cpu": time.process_time(),
                },
                sort_keys=True,
            )
            + "\n"
        )
        self._trace.flush()

    def close(self):
        if self._trace is not None and not self._trace.closed:
            faulthandler.cancel_dump_traceback_later()
            self._trace.close()


probe = CrashProbe()
