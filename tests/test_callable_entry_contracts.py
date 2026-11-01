"""Static callable admission and direct executable drift at real dispatch boundaries."""

import asyncio
from functools import partial

import pytest

from relf_agent import (
    AgentSpec,
    LocalEngine,
    ModelResponse,
    Scope,
    SQLiteStore,
    ToolCall,
    ToolRegistry,
    ToolSpec,
)
from relf_agent.errors import DefinitionMismatch, ValidationError
from relf_agent.executors import DispatchEnvelope, PythonToolExecutor
from relf_agent.types import InvocationContext, digest


def registry_with(handler, reconciler=None):
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "change",
            "Change",
            {"type": "object"},
            effect="unqueryable_write",
            requires_approval=True,
        ),
        handler,
        reconciler=reconciler,
    )
    return registry


def envelope_for(registry):
    return DispatchEnvelope(
        InvocationContext(Scope(), "run", "action", "attempt", "effect", "epoch"),
        registry.get("change").manifest,
        {},
        "operation",
    )


class Provider:
    identity = {"kind": "callable-entry-fixture", "version": "1"}

    async def complete(self, messages, tools):
        if any(message["role"] == "tool" for message in messages):
            return ModelResponse(output="done")
        return ModelResponse(tool_calls=[ToolCall("change", {})])


def property_handler(calls):
    namespace = {"__name__": __name__, "calls": calls}
    exec(
        "def entry(self):\n"
        "    calls.append('getter')\n"
        "    return self.run\n"
        "def replacement(self):\n"
        "    calls.append('replacement')\n"
        "    return self.run\n"
        "def run(self, arguments, context):\n"
        "    calls.append('run')\n"
        "    return {'committed': True}\n",
        namespace,
    )
    owner = type(
        "PropertyHandler",
        (),
        {"__call__": property(namespace["entry"]), "run": namespace["run"]},
    )
    owner.__module__ = __name__
    return owner(), namespace["replacement"]


@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_unchanged_property_callable_executes_without_validation_getters(operation):
    calls = []
    handler, _ = property_handler(calls)
    registry = registry_with(handler, handler if operation == "reconcile" else None)
    envelope = envelope_for(registry)
    registry.get("change").validate({})
    registry.get("change").check()
    assert calls == []
    observation = asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))
    assert observation.result == {"committed": True}
    assert calls == ["getter", "run"]


@pytest.mark.parametrize("operation", ["execute", "reconcile"])
@pytest.mark.parametrize("mutation", ["replacement", "code"])
def test_property_getter_drift_is_rejected_without_invoking_getter(operation, mutation):
    calls = []
    handler, replacement = property_handler(calls)
    registry = registry_with(handler, handler if operation == "reconcile" else None)
    envelope = envelope_for(registry)
    if mutation == "replacement":
        type(handler).__call__ = property(replacement)
    else:
        type(handler).__call__.fget.__code__ = replacement.__code__
    with pytest.raises(DefinitionMismatch):
        asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))
    assert registry.get("change").handler is handler  # Cleanup remains reachable.
    assert calls == []


def constructor_handler(calls, inherited):
    class Meta(type):
        def __call__(cls, arguments, context):
            calls.append("meta")
            return type.__call__(cls, arguments, context)

    class Handler(dict, metaclass=Meta):
        def __new__(cls, arguments, context):
            calls.append("new")
            return dict.__new__(cls)

        def __init__(self, arguments, context):
            calls.append("init")
            dict.__init__(self, committed=True)

    class InheritedMeta(Meta):
        pass

    class Child(Handler, metaclass=InheritedMeta):
        pass

    def replacement(receiver, arguments, context):
        calls.append("replacement")
        return {"committed": False}

    return (Child if inherited else Handler), Handler, Meta, replacement


@pytest.mark.parametrize("inherited", [False, True])
@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_unchanged_constructor_executes_and_reconciles(inherited, operation):
    calls = []
    handler, _, _, _ = constructor_handler(calls, inherited)
    registry = registry_with(handler, handler if operation == "reconcile" else None)
    envelope = envelope_for(registry)
    assert calls == []
    observation = asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))
    assert observation.result == {"committed": True}
    assert calls == ["meta", "new", "init"]


@pytest.mark.parametrize("entry", ["__call__", "__new__", "__init__"])
@pytest.mark.parametrize("inherited", [False, True])
@pytest.mark.parametrize("mutation", ["replacement", "code"])
@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_constructor_direct_and_inherited_entry_drift_blocks_dispatch(
    entry, inherited, mutation, operation
):
    calls = []
    handler, owner, meta, replacement = constructor_handler(calls, inherited)
    registry = registry_with(handler, handler if operation == "reconcile" else None)
    envelope = envelope_for(registry)
    target = meta if entry == "__call__" else owner
    if mutation == "code":
        getattr(target, entry).__code__ = replacement.__code__
    else:
        setattr(target, entry, staticmethod(replacement) if entry == "__new__" else replacement)
    with pytest.raises(DefinitionMismatch):
        asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))
    assert registry.get("change").handler is handler
    assert calls == []


@pytest.mark.parametrize("role", ["handler", "reconciler"])
@pytest.mark.parametrize("opaque", ["custom", "property-subclass"])
def test_opaque_call_descriptor_fails_admission_without_running_getter(role, opaque):
    calls = []

    class Descriptor:
        def __get__(self, instance, owner):
            calls.append("getter")
            return lambda arguments, context: {}

    class CustomProperty(property):
        def __get__(self, instance, owner):
            calls.append("getter")
            return lambda arguments, context: {}

    descriptor = Descriptor() if opaque == "custom" else CustomProperty(lambda self: None)
    handler = type("Opaque", (), {"__call__": descriptor})()
    registry = ToolRegistry()
    with pytest.raises(ValidationError, match="[Uu]nsupported.*[Dd]escriptor"):
        registry.register(
            ToolSpec("opaque", "Opaque", {"type": "object"}),
            handler if role == "handler" else lambda arguments, context: {},
            reconciler=handler if role == "reconciler" else None,
        )
    with pytest.raises(DefinitionMismatch, match="not registered"):
        registry.get("opaque")
    assert calls == []


def test_property_callable_keeps_original_persisted_manifest_shape():
    handler, _ = property_handler([])
    registry = registry_with(handler)
    assert registry.get("change").manifest == {
        "name": "change",
        "description": "Change",
        "input_schema": {"type": "object"},
        "version": "1",
        "effect": "unqueryable_write",
        "requires_approval": True,
        "cost": 1,
        "config": {},
        "implementation_digest": digest(
            [{"module": __name__, "name": "PropertyHandler", "source": None}, None]
        ),
    }


def test_constructor_code_change_cannot_use_original_approved_action(tmp_path):
    async def scenario():
        calls = []
        handler, owner, _, replacement = constructor_handler(calls, False)
        registry = registry_with(handler)
        with LocalEngine(
            SQLiteStore(tmp_path / "constructor.sqlite"),
            providers={"default": Provider()},
            tools=registry,
        ) as engine:
            receipt = engine.submit(AgentSpec("a", "A", ("change",)), "change", command_id="s")
            waiting = await engine.drive(receipt.run_id)
            pending = waiting.pending[0]
            owner.__init__.__code__ = replacement.__code__
            try:
                engine.approve(
                    receipt.run_id, pending["action_id"], pending["digest"], command_id="a"
                )
                await engine.drive(receipt.run_id)
            except DefinitionMismatch:
                pass
            assert calls == []
            assert engine.status(receipt.run_id).state != "succeeded"

    asyncio.run(scenario())


@pytest.mark.parametrize("form", ["builtin", "partial-property"])
def test_stable_builtin_entries_and_partial_property_subclasses_are_accepted(form):
    class Handler(partial):
        @property
        def __call__(self):
            return self.func

    handler = {"builtin": dict, "partial-property": Handler(dict)}[form]
    registry = registry_with(handler)
    for _ in range(3):
        registry.get("change").check()
        registry.manifests(["change"])


def test_partial_subclass_func_shadow_is_rejected_without_running_getter():
    calls = []

    def run(arguments, context):
        calls.append("run")
        return {"committed": True}

    class Handler(partial):
        @property
        def func(self):
            calls.append("getter")
            return run

    with pytest.raises(ValidationError, match="Unsupported callable descriptor.*partial.func"):
        registry_with(Handler(run))
    assert calls == []


def test_standalone_builtin_method_wrapper_fails_admission_with_clear_error():
    registry = ToolRegistry()
    with pytest.raises(ValidationError, match="[Uu]nsupported.*[Cc]allable"):
        registry.register(ToolSpec("wrapper", "Wrapper", {"type": "object"}), {}.__or__)
    with pytest.raises(DefinitionMismatch, match="not registered"):
        registry.get("wrapper")


@pytest.mark.parametrize("form", ["property", "constructor"])
@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_queued_property_and_constructor_drift_is_rechecked_in_worker(form, operation):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    async def scenario():
        calls = []
        if form == "property":
            handler, replacement = property_handler(calls)
            original = type(handler).__call__.fget
        else:
            handler, owner, _, replacement = constructor_handler(calls, True)
            original = owner.__init__
        registry = registry_with(handler, handler if operation == "reconcile" else None)
        envelope = envelope_for(registry)
        loop = asyncio.get_running_loop()
        release = threading.Event()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        blocker = loop.run_in_executor(None, release.wait)
        task = asyncio.create_task(getattr(PythonToolExecutor(registry), operation)(envelope))
        try:
            await asyncio.sleep(0)
            original.__code__ = replacement.__code__
        finally:
            release.set()
        await blocker
        with pytest.raises(DefinitionMismatch):
            await task
        assert calls == []

    asyncio.run(scenario())


@pytest.mark.parametrize("form", ["property", "constructor"])
@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_inflight_property_and_constructor_drift_cannot_be_adopted(form, operation):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        namespace = {"__name__": __name__, "started": started, "release": release}
        exec(
            "async def run(self, arguments, context):\n"
            "    started.set()\n"
            "    await release.wait()\n"
            "    return {'committed': True}\n"
            "async def replacement(self, arguments, context):\n"
            "    started.set()\n"
            "    await release.wait()\n"
            "    return {'committed': False}\n"
            "def getter(self):\n"
            "    return self.run\n"
            "def replacement_getter(self):\n"
            "    return self.run\n",
            namespace,
        )
        if form == "property":
            handler = type(
                "Handler", (), {"__call__": property(namespace["getter"]), "run": namespace["run"]}
            )()
            original, replacement = namespace["getter"], namespace["replacement_getter"]
        else:
            meta = type("Meta", (type,), {"__call__": namespace["run"]})
            handler = meta("Handler", (dict,), {})
            original, replacement = namespace["run"], namespace["replacement"]
        registry = registry_with(handler, handler if operation == "reconcile" else None)
        task = asyncio.create_task(
            getattr(PythonToolExecutor(registry), operation)(envelope_for(registry))
        )
        await asyncio.wait_for(started.wait(), 2)
        original.__code__ = replacement.__code__
        release.set()
        with pytest.raises(DefinitionMismatch):
            await task

    asyncio.run(scenario())


@pytest.mark.parametrize("entry", ["staticmethod", "classmethod", "metaclass-property"])
def test_standard_descriptor_binding_is_stable_and_getter_code_is_pinned(entry):
    calls = []

    def run(*arguments):
        calls.append("run")
        return {"committed": True}

    def replacement(*arguments):
        calls.append("replacement")
        return {"committed": False}

    def getter(cls):
        calls.append("getter")
        return run

    def replacement_getter(cls):
        calls.append("replacement-getter")
        return run

    if entry == "metaclass-property":
        meta = type("Meta", (type,), {"__call__": property(getter)})
        handler = meta("Handler", (dict,), {})
        original, changed = getter, replacement_getter
        expected_calls = ["getter", "run"]
    else:
        descriptor = staticmethod(run) if entry == "staticmethod" else classmethod(run)
        handler = type("Handler", (), {"__call__": descriptor})()
        original, changed = run, replacement
        expected_calls = ["run"]
    registry = registry_with(handler)
    envelope = envelope_for(registry)
    assert calls == []
    executor = PythonToolExecutor(registry)
    assert asyncio.run(executor.execute(envelope)).result == {"committed": True}
    assert calls == expected_calls
    original.__code__ = changed.__code__
    with pytest.raises(DefinitionMismatch):
        asyncio.run(executor.execute(envelope))
    assert calls == expected_calls


@pytest.mark.parametrize("form", ["class-method", "instance-method"])
@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_captured_builtin_remains_callable_after_owner_attribute_replacement(form, operation):
    if form == "class-method":

        class Owner(dict):
            pass

        captured = Owner.fromkeys
        expected = {}

        def replacement(cls, arguments, context):
            return {"implementation": "replacement"}

        def replace_attribute():
            Owner.fromkeys = classmethod(replacement)

    else:

        class Owner(str):
            pass

        captured = Owner("original").format
        expected = "original"

        def replacement(self, arguments, context):
            return "replacement"

        def replace_attribute():
            Owner.format = replacement

    def handler(arguments, context):
        return {"handler": True}

    registry = registry_with(
        captured if operation == "execute" else handler,
        captured if operation == "reconcile" else None,
    )
    envelope = envelope_for(registry)
    replace_attribute()
    assert captured({}, None) == expected
    registry.get("change").check()
    assert registry.manifests(["change"]) == {"change": envelope.tool_manifest}
    observation = asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))
    assert observation.result == expected
