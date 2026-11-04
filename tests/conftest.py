"""Bounded teardown for clients whose test runtime intentionally retains debt."""

import sys

import pytest

from .host_awake import keep_awake


@pytest.fixture(scope="session", autouse=True)
def preserve_local_test_execution_host():
    with keep_awake() as process:
        yield None if process is None else process.pid


@pytest.fixture(autouse=True)
def detach_retained_coding_clients_after_original_loop():
    yield
    resources = sys.modules.get("tests.temporal_fixture_resources")
    if resources is not None:
        resources.retained.finish()
