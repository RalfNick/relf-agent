"""A replacement read port cannot silently change the replayed command."""

import inspect
import threading
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace

import pytest

from relf_agent import AgentSpec, RuntimeBuilder, RuntimeCatalog, RuntimeProfile
from relf_agent.errors import ValidationError
from relf_agent.runtime_router import ProfiledEngine, SQLiteRunReader
from relf_agent.types import CommandReceipt


@pytest.fixture
def replay(tmp_path):
    path = tmp_path / "runs.sqlite"
    profile = RuntimeProfile("app", "1", {"default": {"adapter": "offline-echo"}})
    catalog = RuntimeCatalog()
    catalog.register(profile, default=True)
    spec = AgentSpec("a", "Answer")
    with RuntimeBuilder().build(profile, path) as original:
        run_id = original.submit(spec, "q", command_id="seed").run_id

    class Builder:
        def build(self, *args, **kwargs):
            pytest.fail("An invalid or completed receipt must not construct an execution runtime")

    class Reader(SQLiteRunReader):
        value = None

        def submit_receipt(self, command_id, payload):
            self.calls.append("submit")
            return self.value

        def command_receipt(self, command_id, kind, payload):
            self.calls.append(kind)
            return self.value

    reader = Reader(path)
    reader.calls = []
    router = ProfiledEngine(catalog, path, builder=Builder(), reader=reader)

    def invoke(kind):
        if kind == "submit":
            return router.submit(spec, "q", command_id=kind).receipt
        if kind == "cancel":
            return router.cancel(run_id, command_id=kind)
        if kind == "approve":
            return router.approve(run_id, "action", "a" * 64, command_id=kind)
        if kind == "reconcile":
            return router.reconcile(run_id, "action", {"confirmed": True}, command_id=kind)
        return router.send_input(run_id, "input:" + "b" * 64, "a" * 64, "answer", command_id=kind)

    yield run_id, reader, invoke
    value = reader.value
    if inspect.iscoroutine(value) or inspect.isgenerator(value):
        value.close()
    assert reader.calls
    assert reader.status(run_id).state == "queued"
    assert reader.events(run_id)[-1].kind == "run_submitted"
    router.close()


@pytest.mark.parametrize("kind", ["submit", "cancel"])
@pytest.mark.parametrize(
    "shape", ["object", "false", "coroutine", "generator", "context", "async-context"]
)
def test_lazy_or_untyped_reader_receipt_is_rejected_without_execution(replay, kind, shape):
    run_id, reader, invoke = replay
    entered = []

    async def coroutine():
        entered.append(True)

    def generator():
        entered.append(True)
        yield

    @contextmanager
    def context():
        entered.append(True)
        yield

    @asynccontextmanager
    async def async_context():
        entered.append(True)
        yield

    factories = {
        "object": dict,
        "false": lambda: False,
        "coroutine": coroutine,
        "generator": generator,
        "context": context,
        "async-context": async_context,
    }
    reader.value = factories[shape]()
    with pytest.raises(ValidationError):
        invoke(kind)
    assert entered == []


KINDS = ["submit", "cancel", "approve", "reconcile", "send_input"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "field,value",
    [
        ("command_id", "other"),
        ("kind", "other"),
        ("record_state", "received"),
        ("apply_state", []),
        ("run_id", ""),
        ("outcome", []),
        ("outcome", {"not-finite": float("nan")}),
    ],
)
def test_reader_receipt_must_match_the_original_request_and_be_finite(replay, kind, field, value):
    run_id, reader, invoke = replay
    reader.value = replace(CommandReceipt(kind, run_id, kind), **{field: value})
    with pytest.raises(ValidationError):
        invoke(kind)


@pytest.mark.parametrize("kind", KINDS[1:])
def test_control_reader_receipt_cannot_target_another_run(replay, kind):
    _, reader, invoke = replay
    reader.value = CommandReceipt(kind, "different-run", kind)
    with pytest.raises(ValidationError):
        invoke(kind)


@pytest.mark.parametrize("kind", KINDS)
def test_valid_replayed_receipt_has_a_detached_outcome(replay, kind):
    run_id, reader, invoke = replay
    reader.value = CommandReceipt(kind, run_id, kind, outcome={"nested": {"values": []}})
    first = invoke(kind)
    assert first == reader.value
    first.outcome["nested"]["values"].append("caller change")
    assert reader.value.outcome == {"nested": {"values": []}}
    assert invoke(kind).outcome == {"nested": {"values": []}}


@pytest.mark.parametrize("kind", KINDS[1:])
def test_rejected_control_receipts_still_replay_as_original_refusals(replay, kind):
    run_id, reader, invoke = replay
    reader.value = CommandReceipt(
        kind,
        run_id,
        kind,
        apply_state="rejected",
        outcome={"rejected": True, "reason": "target_closed"},
    )
    assert invoke(kind) == reader.value


@pytest.mark.parametrize("kind", ["submit", "cancel"])
def test_recursive_receipt_outcomes_are_typed_configuration_errors(replay, kind):
    run_id, reader, invoke = replay
    outcome = {}
    outcome["self"] = outcome
    reader.value = CommandReceipt(kind, run_id, kind, outcome=outcome)
    with pytest.raises(ValidationError):
        invoke(kind)


def test_rejected_submit_receipt_is_not_a_successful_run_handle(replay):
    run_id, reader, invoke = replay
    reader.value = CommandReceipt("submit", run_id, "submit", apply_state="rejected")
    with pytest.raises(ValidationError):
        invoke("submit")


def test_default_reader_preserves_native_whitespace_command_identity(tmp_path):
    path = tmp_path / "native.sqlite"
    profile = RuntimeProfile("native", "1", {"default": {"adapter": "offline-echo"}})
    catalog = RuntimeCatalog()
    catalog.register(profile, default=True)
    spec = AgentSpec("a", "Answer")
    with RuntimeBuilder().build(profile, path) as original:
        expected = original.submit(spec, "q", command_id=" ")
    with ProfiledEngine(catalog, path) as router:
        assert router.submit(spec, "q", command_id=" ") == expected


@pytest.mark.parametrize("kind", ["submit", "cancel"])
@pytest.mark.parametrize("shape", ["coroutine", "thread-lock"])
def test_non_json_native_fields_are_typed_errors_without_entering_them(replay, kind, shape):
    run_id, reader, invoke = replay
    entered = []

    async def coroutine():
        entered.append(True)

    value = coroutine() if shape == "coroutine" else threading.Lock()
    reader.value = CommandReceipt(kind, run_id, kind, outcome={"native": value})
    try:
        with pytest.raises(ValidationError):
            invoke(kind)
        assert entered == []
    finally:
        if inspect.iscoroutine(value):
            value.close()
