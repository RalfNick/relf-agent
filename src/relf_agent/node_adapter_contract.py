"""Fixed Local NodeExecutor checks under the original Tool Action authority.

Fixtures provide concrete components and fault controls, never verdicts or Run
receipts. Original engines and resource owners survive incomplete cleanup.
"""

import asyncio
import copy
import inspect
from collections import deque
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Protocol

from .adapter_contract_catalog import catalog_for
from .adapter_contract_types import AdapterContractCaseResult, AdapterContractCleanupPending
from .errors import DefinitionMismatch, ValidationError
from .ports import is_async_callable
from .runtime_lifecycle import BuildContext
from .types import Scope, canonical, digest


class NodeAdapterFixture(Protocol):
    def prepare(self, case_id: str, workspace: Path) -> "NodeContractSession":
        """Prepare a concrete component and its owners, synchronously or asynchronously."""
        ...


@dataclass(frozen=True)
class NodeContractResource:
    resource: object
    asynchronous: bool = False

    def __post_init__(self):
        if type(self.asynchronous) is not bool:
            raise ValidationError("Node contract resource close mode must be boolean")


@dataclass(frozen=True)
class NodeContractPause:
    wait_entered: Callable
    release: Callable

    def __post_init__(self):
        if not callable(self.wait_entered) or not callable(self.release):
            raise ValidationError("Node contract pause requires callable management hooks")


@dataclass(frozen=True)
class NodeContractSession:
    """Borrowed component, explicit owners and bounded management callbacks.

    configure('output', {'result': value}) and configure('reset', {}) complete
    with None. inject_fault supports identity-drift/method-drift/handler-error/
    reset. pause('execute') returns NodeContractPause; audit returns only integer
    execute_calls/reconcile_calls/close_calls. reopen reconnects the same
    component without changing its identity or cumulative counters.
    """

    component: object
    resources: tuple[NodeContractResource, ...] = ()
    configure: Callable | None = None
    inject_fault: Callable | None = None
    pause: Callable | None = None
    audit: Callable | None = None
    reopen: Callable | None = None

    def __post_init__(self):
        if (
            not isinstance(self.resources, (tuple, list))
            or len(self.resources) > 16
            or any(type(value) is not NodeContractResource for value in self.resources)
            or any(
                value is not None and not callable(value)
                for value in (
                    self.configure,
                    self.inject_fault,
                    self.pause,
                    self.audit,
                    self.reopen,
                )
            )
        ):
            raise ValidationError("Node contract fixture requires bounded concrete resources")
        object.__setattr__(self, "resources", tuple(self.resources))


@dataclass
class _CaseControl:
    cancelled: asyncio.Event
    resets: list
    owners: object
    audit_before: dict | None = None
    pending_work: list = field(default_factory=list)
    observed_work: list = field(default_factory=list)
    pending_lazy: list = field(default_factory=list)
    observed_lazy: list = field(default_factory=list)


_current_case: ContextVar[_CaseControl | None] = ContextVar("node_contract_case", default=None)


class _Violation(Exception):
    pass


class _Missing(Exception):
    pass


class _InvalidReturn(_Violation):
    """A rejected return whose already-started work has been fully drained."""


class _ReturnedWorkPending(_Violation):
    """A visible original future could not be awaited and remains unfinished."""


@dataclass
class _ResourceDeclaration:
    entry: NodeContractResource
    owner: BuildContext
    adopted: bool = False


class _ResourceOwners:
    """Keep rejected declarations as original debts, separate from accepted owners."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.declarations = []
        self.completed = []
        self.sessions = []

    @staticmethod
    def _adopt(declaration):
        entry, owner = declaration.entry, declaration.owner
        (owner.own_async if entry.asynchronous else owner.own)(entry.resource)
        declaration.adopted = True

    def adopt(self, session):
        if any(original is session for original in self.sessions):
            return False, False
        self.sessions.append(session)
        failed = cancelled = False
        for entry in session.resources:
            previous = next(
                (
                    declaration
                    for declaration in (*self.declarations, *self.completed)
                    if declaration.entry.resource is entry.resource
                ),
                None,
            )
            if previous is not None:
                failed |= previous.entry.asynchronous != entry.asynchronous
                continue
            declaration = _ResourceDeclaration(
                entry,
                BuildContext(
                    None,
                    self.workspace / "unused.sqlite",
                    Scope("node-contract", "owner"),
                    self.workspace,
                    allow_async=True,
                ),
            )
            # Retain ownership intent before inspecting an arbitrary close descriptor.
            self.declarations.append(declaration)
            try:
                self._adopt(declaration)
            except asyncio.CancelledError:
                failed = cancelled = True
            except Exception:
                failed = True
        return failed, cancelled

    async def cleanup_async(self):
        for declaration in tuple(reversed(self.declarations)):
            if not declaration.adopted:
                self._adopt(declaration)
            # Every unresolved declaration keeps earlier dependencies alive.
            # Later valid owners have already been visited in this reverse walk.
            await declaration.owner.cleanup_async()
            self.declarations[:] = [
                value for value in self.declarations if value is not declaration
            ]
            self.completed.append(declaration)


def _check(condition):
    if not condition:
        raise _Violation()


def _active():
    control = _current_case.get()
    if control is not None and control.cancelled.is_set():
        raise asyncio.CancelledError()


def _required(session, *names):
    if any(getattr(session, name) is None for name in names):
        raise _Missing()


def _discover_return(value, *, rejected=False):
    """Record the entire visible return graph before waiting or closing anything."""
    control = _current_case.get()
    queue, seen, invalid = deque(((value, rejected),)), set(), False
    while queue:
        value, rejected = queue.popleft()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if asyncio.isfuture(value):
            _retain_work(value)
            invalid = True
            if value.done():
                try:
                    result = value.result()
                except (Exception, asyncio.CancelledError):
                    continue
                queue.append((result, True))
        elif inspect.iscoroutine(value) or inspect.isgenerator(value):
            invalid = True
            if not any(original is value for original in control.observed_lazy):
                control.observed_lazy.append(value)
                control.pending_lazy.append(value)
        elif type(value) is NodeContractSession and rejected:
            control.owners.adopt(value)
            invalid = True
        elif type(value) is dict:
            # Keys can themselves be futures in an already-invalid mapping.
            queue.extend((item, True) for item in (*value.keys(), *value.values()))
        elif type(value) in {list, tuple, set, frozenset}:
            queue.extend((item, True) for item in value)
    return invalid


async def _dispose(value, *, rejected=False):
    invalid = _discover_return(value, rejected=rejected)
    if invalid:
        await _drain_returned_work()
    return invalid


def _retain_work(value):
    control = _current_case.get()
    if not any(original is value for original in control.observed_work):
        control.observed_work.append(value)
        control.pending_work.append(value)


async def _drain_returned_work():
    control = _current_case.get()
    while control.pending_lazy or control.pending_work:
        while control.pending_lazy:
            original = control.pending_lazy[0]
            # Do not execute an unstarted coroutine to discover its result.
            original.close()
            control.pending_lazy.pop(0)
        if not control.pending_work:
            break
        original = control.pending_work[0]
        await _finish(original)
        if not original.done():
            raise _ReturnedWorkPending()
        control.pending_work.pop(0)
        try:
            result = original.result()
        except (Exception, asyncio.CancelledError):
            continue
        _discover_return(result, rejected=True)


async def _invoke(method, *args):
    value = method(*args)
    if asyncio.isfuture(value):
        await _finish(value)
        if not value.done():
            _retain_work(value)
            raise _ReturnedWorkPending()
        value = value.result()
    elif inspect.isawaitable(value):
        value = await value
    if await _dispose(value):
        raise _InvalidReturn()
    return value


async def _manage(method, *args):
    value = await _invoke(method, *args)
    if value is not None:
        raise _Violation()


async def _configure(session, kind, data):
    _active()
    _required(session, "configure")
    await _manage(session.configure, kind, copy.deepcopy(data))
    _active()


async def _fault(session, kind):
    _active()
    _required(session, "inject_fault")
    control = _current_case.get()
    if (
        kind != "reset"
        and control is not None
        and not any(value is session for value in control.resets)
    ):
        control.resets.append(session)
    try:
        await _manage(session.inject_fault, kind)
    except (_InvalidReturn, _ReturnedWorkPending):
        # The original returned task has finished. Do not invoke reset twice.
        if kind == "reset" and control is not None:
            control.resets[:] = [value for value in control.resets if value is not session]
        raise
    if kind == "reset" and control is not None:
        control.resets[:] = [value for value in control.resets if value is not session]
    _active()


async def _audit(session):
    value = await _invoke(session.audit)
    _check(
        type(value) is dict and set(value) <= {"execute_calls", "reconcile_calls", "close_calls"}
    )
    _check(all(type(count) is int and 0 <= count <= 2**63 - 1 for count in value.values()))
    return copy.deepcopy(value)


async def _case_audit(session):
    _active()
    value = await _audit(session)
    _active()
    return value


def _delta(before, after, *keys):
    if any(key not in before or key not in after for key in keys):
        raise _Missing()
    _check(all(after[key] >= before[key] for key in keys))
    return {key: after[key] - before[key] for key in keys}


def _identity(component):
    value = getattr(component, "identity", None)
    _check(type(value) is dict and bool(value))
    canonical(value)
    _check(is_async_callable(getattr(component, "execute", None)))
    return copy.deepcopy(value)


def _same_json(left, right):
    return canonical(left) == canonical(right)


def _generic():
    return {"items": [None, False, 0, "中文🙂", {"nested": [1, 2]}]}


def _config():
    return {"mode": "full", "nested": {"values": [0, False]}}


def _registry(session, **options):
    from .workflow_executors import NodeExecutorRegistry, NodeExecutorSpec

    registry = NodeExecutorRegistry()
    registry.register(
        NodeExecutorSpec("probe", "Node contract probe", effect="read_only", cost=2, **options),
        session.component,
    )
    return registry


def _engine(session, workspace, engines, *, path=None, **options):
    from .engine import LocalEngine
    from .storage import SQLiteStore
    from .tools import ToolRegistry

    _active()
    registry = _registry(session, **options)
    store = SQLiteStore(path or workspace / f"consumer-{len(engines)}.sqlite")
    try:
        engine = LocalEngine(
            store,
            providers={},
            tools=ToolRegistry(),
            workflow_executors=registry,
            scope=Scope("node-contract", "owner"),
        )
    except BaseException:
        store.close()
        raise
    engines.append(engine)
    return engine


def _graph(config=None):
    from .workflow import GraphNode, GraphWorkflowSpec, ValueRef

    return GraphWorkflowSpec(
        "node-contract",
        [GraphNode("probe", executor="probe", config=config or {})],
        output=ValueRef("probe"),
    )


def _admit(engine, runs, *, input=None, config=None, budget=2, command=None):
    _active()
    spec = _graph(config)
    handle = engine.submit(spec, input, command_id=command or f"submit-{len(runs)}", budget=budget)
    runs.append((engine, handle.run_id))
    return handle, spec


async def _drive(engine, run_id):
    _active()
    value = await engine.drive(run_id)
    _active()
    return value


def _actions(record):
    return [action for action in record["actions"] if action["kind"] == "tool"]


def _settled(engine, run_id):
    _check(engine.store.budget(run_id) == {"limit": 2, "held": 0, "spent": 2})
    reservations = list(
        engine.store.conn.execute("SELECT * FROM reservations WHERE run_id=?", (run_id,))
    )
    _check(len(reservations) == 1)
    _check(reservations[0]["state"] == "settled" and reservations[0]["actual"] == 2)


def _confirmed(engine, run_id, output):
    record = engine.store.run(run_id)
    actions = _actions(record)
    _check(len(record["actions"]) == len(actions) == 1)
    action = actions[0]
    _check(action["status"] == "completed" and _same_json(action["result"], output))
    _check(_same_json(action["effect_observation"]["result"], output))
    _check(len(action["attempts"]) == 1 and action["attempts"][0]["status"] == "completed")
    _settled(engine, run_id)
    return action


async def _finish(task):
    interrupted = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            interrupted = True
        except Exception:
            break
    return interrupted


class _PausedCallPending(Exception):
    def __init__(self, task, release, *, released=False):
        super().__init__("Original Node handler cleanup remains incomplete")
        self.task, self.release, self.released = task, release, released

    async def cleanup(self):
        if not self.released:
            try:
                await _manage(self.release)
            except _InvalidReturn:
                pass
            except _ReturnedWorkPending:
                self.released = True
                raise
            self.released = True
        await _finish(self.task)
        if not self.task.cancelled():
            self.task.exception()


async def _entered(pause, operation):
    waiter = asyncio.create_task(_manage(pause.wait_entered))
    control = _current_case.get()
    cancellation = asyncio.create_task(control.cancelled.wait())
    try:
        done, _ = await asyncio.wait(
            (waiter, operation, cancellation), return_when=asyncio.FIRST_COMPLETED
        )
        _active()
        if operation in done:
            operation.result()
            raise _Violation()
        waiter.result()
        _check(not operation.done())
    finally:
        for observer in (waiter, cancellation):
            if not observer.done():
                observer.cancel()
            await _finish(observer)
            if not observer.cancelled():
                observer.exception()


def _handler_suspended(session, engine, run_id):
    """Confirm the actual registered handler is suspended, not only a fixture flag."""
    action = _actions(engine.store.run(run_id))[0]
    _check(action["status"] == "executing" and action["attempts"][-1]["status"] == "executing")
    task = engine._inflight.get(run_id)
    _check(task is not None and not task.done())
    method = session.component.execute
    while isinstance(method, partial):
        method = method.func
    code = getattr(getattr(method, "__func__", method), "__code__", None)
    if code is None:
        # Inspect the registered callable's code, rather than testing callability.
        method = inspect.getattr_static(method, "__call__", None)
        code = getattr(getattr(method, "__func__", method), "__code__", None)
    frame, seen = task.get_coro(), set()
    while inspect.iscoroutine(frame) and id(frame) not in seen:
        seen.add(id(frame))
        if frame.cr_code is code:
            _check(inspect.getcoroutinestate(frame) == inspect.CORO_SUSPENDED)
            return
        frame = frame.cr_await
    raise _Violation()


async def _lifecycle(session, workspace, observations, engines, runs):
    from .coordinator import FileCoordinator
    from .errors import CoordinatorBusy

    _required(session, "configure", "pause")
    await _configure(session, "output", {"result": _generic()})
    engine = _engine(session, workspace, engines)
    handle, _ = _admit(engine, runs, input=_generic(), config=_config())
    before = await _case_audit(session)
    pause = await _invoke(session.pause, "execute")
    _check(type(pause) is NodeContractPause)
    task = asyncio.create_task(engine.drive(handle.run_id))
    handler, released = None, False

    async def release_original():
        nonlocal released
        if not released:
            try:
                await _manage(pause.release)
            except (_InvalidReturn, _ReturnedWorkPending):
                released = True
                raise
            released = True

    try:
        await _entered(pause, task)
        _handler_suspended(session, engine, handle.run_id)
        handler = engine._inflight[handle.run_id]
        original_action = _actions(engine.store.run(handle.run_id))[0]
        # Cancel the actual public drive caller. Local retains its original
        # handler and records business cancellation, rather than cancelling I/O.
        task.cancel()
        await _finish(task)
        _check(task.cancelled() and not handler.done())
        _check(engine._inflight.get(handle.run_id) is handler)
        try:
            await engine.drive(handle.run_id)
        except CoordinatorBusy:
            pass
        else:
            raise _Violation()
        try:
            engine.close()
        except ValidationError:
            observations["rejection_checks"] = 1
        else:
            raise _Violation()
        contender = FileCoordinator(str(engine.store.path) + ".coordinator")
        try:
            contender.acquire()
        except CoordinatorBusy:
            pass
        else:
            contender.release()
            raise _Violation()
        _check(_same_json(engine.store.budget(handle.run_id), {"limit": 2, "held": 2, "spent": 0}))
        _check((await _case_audit(session))["close_calls"] == before["close_calls"])
        await release_original()
        await _finish(handler)
        handler.result()
        done = await _drive(engine, handle.run_id)
        _check(done.state == "cancelled")
        action = _confirmed(engine, handle.run_id, _generic())
        _check(
            all(
                _same_json(action[key], original_action[key])
                for key in ("id", "effect_key", "digest")
            )
        )
        _check(_delta(before, await _case_audit(session), "execute_calls")["execute_calls"] == 1)
        observations.update(cancelled=True, handler_finished=True, settlement_checks=1)
    finally:
        try:
            await release_original()
        except (Exception, asyncio.CancelledError):
            raise _PausedCallPending(handler or task, pause.release, released=released) from None
        if _current_case.get().pending_work:
            raise _PausedCallPending(handler or task, pause.release, released=released)
        for original in (task, handler):
            if original is not None:
                await _finish(original)
                if not original.cancelled():
                    original.exception()


def _capture(engine, runs, records):
    for owner, run_id in runs:
        if owner is engine:
            records[run_id] = engine.store.run(run_id)


async def _reopen(session, workspace, observations, engines, runs, records):
    _required(session, "configure", "reopen")
    await _configure(session, "output", {"result": _generic()})
    engine = _engine(session, workspace, engines, requires_approval=True)
    path = engine.store.path
    poor, _ = _admit(engine, runs, input=_generic(), budget=1, command="budget")
    waiting = await _drive(engine, poor.run_id)
    _check(waiting.state == "waiting_approval" and len(waiting.pending) == 1)
    poor_pending = waiting.pending[0]
    engine.approve(
        poor.run_id, poor_pending["action_id"], poor_pending["digest"], command_id="approve-budget"
    )
    rejected = await _drive(engine, poor.run_id)
    _check(rejected.state == "failed")
    _check(engine.store.budget(poor.run_id) == {"limit": 1, "held": 0, "spent": 0})
    _check(not any(action["attempts"] for action in _actions(engine.store.run(poor.run_id))))
    _check(
        (await _case_audit(session))["execute_calls"]
        == _current_case.get().audit_before["execute_calls"]
    )
    handle, spec = _admit(engine, runs, input=_generic(), command="approved")
    waiting = await _drive(engine, handle.run_id)
    _check(waiting.state == "waiting_approval" and len(waiting.pending) == 1)
    pending = waiting.pending[0]
    _check(engine.store.budget(handle.run_id) == {"limit": 2, "held": 0, "spent": 0})
    original_identity = _identity(session.component)
    before = await _case_audit(session)
    _capture(engine, runs, records)
    engine.close()
    engines.remove(engine)
    await _manage(session.reopen)
    _active()
    _check(_same_json(_identity(session.component), original_identity))
    after = await _case_audit(session)
    _check(
        _delta(before, after, "execute_calls", "reconcile_calls")
        == {"execute_calls": 0, "reconcile_calls": 0}
    )
    engine = _engine(session, workspace, engines, path=path, requires_approval=True)
    duplicate = engine.submit(spec, _generic(), command_id="approved", budget=2)
    runs.append((engine, duplicate.run_id))
    _check(duplicate.run_id == handle.run_id and duplicate.receipt == handle.receipt)
    engine.approve(handle.run_id, pending["action_id"], pending["digest"], command_id="approve")
    done = await _drive(engine, handle.run_id)
    _check(done.state == "succeeded" and _same_json(done.result, _generic()))
    _confirmed(engine, handle.run_id, _generic())
    replay = engine.submit(spec, _generic(), command_id="approved", budget=2)
    _check(replay.run_id == handle.run_id)
    _check((await _drive(engine, handle.run_id)).state == "succeeded")
    _check(_delta(before, await _case_audit(session), "execute_calls")["execute_calls"] == 1)
    observations.update(rejection_checks=1, duplicate_checks=2, settlement_checks=1)


async def _case(case_id, session, workspace, observations, engines, runs, records):
    _active()
    _required(session, "audit")
    before = await _case_audit(session)
    if not {"execute_calls", "reconcile_calls", "close_calls"} <= set(before):
        raise _Missing()
    _current_case.get().audit_before = before
    _identity(session.component)
    registry = _registry(session)
    descriptor = registry.get("probe")
    _check(descriptor.component is session.component)
    manifest = descriptor.manifest
    manifest["component"]["mutated"] = True
    _check("mutated" not in registry.get("probe").manifest["component"])
    observations.update(ports_valid=True, identity_valid=True)
    if case_id == "N01":
        return
    if case_id == "N09":
        await _reopen(session, workspace, observations, engines, runs, records)
        return
    if case_id == "N10":
        await _lifecycle(session, workspace, observations, engines, runs)
        return
    if case_id in {"N03", "N04"}:
        options = {
            "input_schema": {"type": "integer"},
            "config_schema": {"type": "object", "maxProperties": 0},
        }
        engine = _engine(session, workspace, engines, **options)
        handle, _ = _admit(
            engine,
            runs,
            input="invalid" if case_id == "N03" else 3,
            config={"invalid": True} if case_id == "N04" else {},
        )
        done = await _drive(engine, handle.run_id)
        _check(done.state == "failed" and done.error == {"code": "validation_error"})
        _check(engine.store.budget(handle.run_id) == {"limit": 2, "held": 0, "spent": 0})
        _check(not any(action["attempts"] for action in _actions(engine.store.run(handle.run_id))))
        _check(_delta(before, await _case_audit(session), "execute_calls")["execute_calls"] == 0)
        observations.update(schema_checks=1, rejection_checks=1)
        return
    if case_id in {"N06", "N07"}:
        _required(session, "inject_fault")
        engine = _engine(session, workspace, engines)
        handle, _ = _admit(engine, runs, input=_generic())
        await _fault(session, "identity-drift" if case_id == "N06" else "method-drift")
        try:
            done = await _drive(engine, handle.run_id)
            _check(done.state == "failed" and done.error == {"code": "definition_mismatch"})
        except DefinitionMismatch:
            pass
        _check(not engine.store.run(handle.run_id)["actions"])
        _check(engine.store.budget(handle.run_id) == {"limit": 2, "held": 0, "spent": 0})
        _check(_delta(before, await _case_audit(session), "execute_calls")["execute_calls"] == 0)
        await _fault(session, "reset")
        observations["rejection_checks"] = 1
        return
    if case_id == "N08":
        _required(session, "inject_fault")
        engine = _engine(session, workspace, engines)
        handle, _ = _admit(engine, runs, input=_generic())
        await _fault(session, "handler-error")
        done = await _drive(engine, handle.run_id)
        _check(done.state == "waiting_reconciliation" and done.error is None)
        action = _actions(engine.store.run(handle.run_id))[0]
        _check(len(action["attempts"]) == 1 and action.get("effect_observation") is None)
        _check(
            action["status"] == "outcome_unknown" and action["attempts"][0]["status"] == "unknown"
        )
        _check(engine.store.budget(handle.run_id) == {"limit": 2, "held": 2, "spent": 0})
        _check(_delta(before, await _case_audit(session), "execute_calls")["execute_calls"] == 1)
        await _fault(session, "reset")
        observations["rejection_checks"] = 1
        return
    _required(session, "configure")
    engine = _engine(
        session,
        workspace,
        engines,
        **({"output_schema": {"type": "integer"}} if case_id == "N05" else {}),
    )
    outputs = (
        ("invalid-output",)
        if case_id == "N05"
        else (None, False, 0, "中文🙂", [1, None, False], _generic())
    )
    for output in outputs:
        await _configure(session, "output", {"result": output})
        input, config = _generic(), _config()
        handle, _ = _admit(engine, runs, input=input, config=config)
        done = await _drive(engine, handle.run_id)
        action = _confirmed(engine, handle.run_id, output)
        _check(_same_json(action["arguments"], {"input": _generic(), "config": _config()}))
        if case_id == "N05":
            _check(done.state == "failed" and done.error == {"code": "validation_error"})
            _check((await _drive(engine, handle.run_id)).state == "failed")
            observations.update(schema_checks=1, rejection_checks=1, duplicate_checks=1)
        else:
            _check(done.state == "succeeded" and _same_json(done.result, output))
            original = engine.store.run(handle.run_id)
            input["items"].append("caller mutation")
            config["nested"]["values"].append("caller mutation")
            action["arguments"]["config"]["nested"]["values"].append("snapshot mutation")
            _check(_same_json(engine.store.run(handle.run_id), original))
        observations["settlement_checks"] = observations.get("settlement_checks", 0) + 1
    _check(
        _delta(before, await _case_audit(session), "execute_calls")["execute_calls"] == len(outputs)
    )


async def run_node_case(case_id, fixture, workspace):
    """Run one frozen case, retaining original operations through cleanup retry."""
    catalog = catalog_for("node-executor", "1", "core")
    if type(case_id) is not str or case_id not in catalog.case_ids:
        raise ValidationError("Unknown NodeExecutor contract case")
    workspace = Path(workspace)
    control = _CaseControl(asyncio.Event(), [], _ResourceOwners(workspace))
    token = _current_case.set(control)
    try:
        return await _run_node_case(case_id, fixture, workspace, control)
    finally:
        _current_case.reset(token)


async def _run_node_case(case_id, fixture, workspace, control):
    observations, engines, runs, records, suspended = {}, [], [], {}, []
    owner, session, task = control.owners, None, None
    adapter_identity = cleanup_pending = None
    status, code, cancelled = "failed", "fixture_prepare_failed", False
    cancellation = control.cancelled
    try:
        prepare = getattr(fixture, "prepare", None)
        _check(callable(prepare))
        preparation = asyncio.create_task(_invoke(prepare, case_id, workspace))
        try:
            session = await asyncio.shield(preparation)
        except asyncio.CancelledError:
            cancelled = True
            cancellation.set()
            await _finish(preparation)
            session = preparation.result()
        if type(session) is not NodeContractSession:
            code = "invalid_fixture_session"
            raise _Violation()
        failed, registration_cancelled = owner.adopt(session)
        if registration_cancelled:
            raise asyncio.CancelledError()
        _check(not failed)
        code = "contract_violation"
        adapter_identity = digest(_identity(session.component))
        if not cancelled:

            async def original_case():
                await _case(case_id, session, workspace, observations, engines, runs, records)

            task = asyncio.create_task(original_case())
            await asyncio.shield(task)
            status, code = "passed", "verified"
    except _Missing:
        status, code = "not_verified", "missing_fixture_capability"
    except _PausedCallPending as pending:
        suspended.append(pending)
        status, code = "failed", "cleanup_failed"
    except asyncio.CancelledError:
        cancelled = True
        cancellation.set()
        for engine, run_id in runs:
            if engine in engines:
                engine.cancel(run_id, command_id="contract-observer-cancel")
        if task is not None:
            await _finish(task)
            if not task.cancelled():
                error = task.exception()
                if isinstance(error, _PausedCallPending):
                    suspended.append(error)
    except Exception:
        status = "failed"
    finally:
        if owner is not None:

            async def cleanup_owned():
                await _drain_returned_work()
                while suspended:
                    await suspended[-1].cleanup()
                    suspended.pop()
                while control.resets:
                    try:
                        await _manage(control.resets[-1].inject_fault, "reset")
                    except _InvalidReturn:
                        # Already-started reset work was drained, never reissued.
                        pass
                    except _ReturnedWorkPending:
                        control.resets.pop()
                        raise
                    control.resets.pop()
                while engines:
                    engine = engines[-1]
                    await engine.wait_for_threads()
                    _capture(engine, runs, records)
                    engine.close()
                    engines.pop()
                    observations["runtime_closed"] = True
                actions = [action for record in records.values() for action in record["actions"]]
                observations.update(
                    source_checks=len(records),
                    tool_calls=sum(
                        len(action["attempts"]) for action in actions if action["kind"] == "tool"
                    ),
                    model_calls=sum(
                        len(action["attempts"]) for action in actions if action["kind"] == "model"
                    ),
                )
                await owner.cleanup_async()

            async def original_cleanup():
                # Retried closures execute outside the original run's context.
                token = _current_case.set(control)
                try:
                    await cleanup_owned()
                finally:
                    _current_case.reset(token)

            cleanup = asyncio.create_task(original_cleanup())
            try:
                cancelled |= await _finish(cleanup)
                cleanup.result()
                observations["cleanup_complete"] = True
            except (Exception, asyncio.CancelledError):
                status, code = "failed", "cleanup_failed"
                observations["cleanup_complete"] = False
                cleanup_pending = original_cleanup
        if type(session) is NodeContractSession and session.audit is not None:
            try:
                auditing = asyncio.create_task(_audit(session))
                cancelled |= await _finish(auditing)
                audited = auditing.result()
                before = control.audit_before
                if before is not None:
                    observations.update(
                        _delta(before, audited, "execute_calls", "reconcile_calls", "close_calls")
                    )
                    if not session.resources:
                        observations["borrowed_closed"] = observations["close_calls"] > 0
                        if observations["borrowed_closed"] and cleanup_pending is None:
                            status, code = "failed", "contract_violation"
            except (Exception, asyncio.CancelledError):
                if cleanup_pending is None:
                    status, code = "failed", "contract_violation"
        # Final audit runs exactly once. Its malformed but observable return may
        # reveal a new owner; finalize that original debt without repeating audit
        # or retrying a resource whose earlier cleanup already failed.
        if cleanup_pending is None and (
            owner.declarations or control.pending_work or control.pending_lazy
        ):
            cleanup = asyncio.create_task(original_cleanup())
            try:
                cancelled |= await _finish(cleanup)
                cleanup.result()
                observations["cleanup_complete"] = True
            except (Exception, asyncio.CancelledError):
                status, code = "failed", "cleanup_failed"
                observations["cleanup_complete"] = False
                cleanup_pending = original_cleanup
    result = AdapterContractCaseResult(
        case_id,
        status,
        code,
        observations,
        adapter_digest=adapter_identity,
        configuration_digest=digest(
            {"contract": "node-executor", "version": "1", "profile": "core"}
        ),
        execution_authority="local" if records else "none",
    )
    if cleanup_pending is not None:
        raise AdapterContractCleanupPending(result, cleanup_pending)
    if cancelled:
        raise asyncio.CancelledError()
    return result
