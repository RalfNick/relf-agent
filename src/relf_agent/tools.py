"""Trusted Python tools with explicit effect contracts and fixed definitions."""

import asyncio
import copy
import inspect
import json
import threading
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from functools import partial
from types import (
    BuiltinFunctionType,
    ClassMethodDescriptorType,
    FunctionType,
    MethodDescriptorType,
    MethodType,
    MethodWrapperType,
    WrapperDescriptorType,
)
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .errors import DefinitionMismatch, ValidationError
from .schema_validation import is_valid
from .types import canonical, credits, digest


class ThreadExecutionTracker:
    """Keep execution ownership until a synchronous callable really exits.

    Cancelling an asyncio Future does not stop its running executor thread.
    Pending calls may be withdrawn, but only the worker can finish a call
    that has begun. Neither transition depends on event-loop callbacks.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._calls: dict[object, tuple[str | None, bool]] = {}
        self._waiters: set[tuple[asyncio.AbstractEventLoop, asyncio.Future]] = set()

    @property
    def has_active(self) -> bool:
        return self.active_count > 0

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._calls)

    def has_active_for(self, group: str) -> bool:
        with self._lock:
            return any(owner == group for owner, _ in self._calls.values())

    def _register(self, group):
        token = object()
        with self._lock:
            self._calls[token] = (group, False)
        return token

    def _begin(self, token):
        with self._lock:
            call = self._calls.get(token)
            if call is None:
                return False
            self._calls[token] = (call[0], True)
            return True

    def _finish(self, token):
        with self._lock:
            self._calls.pop(token, None)
            waiters = tuple(self._waiters)
        self._notify(waiters)

    def _withdraw_pending(self, token):
        with self._lock:
            call = self._calls.get(token)
            if call is not None and not call[1]:
                self._calls.pop(token)
                waiters = tuple(self._waiters)
            else:
                waiters = ()
        self._notify(waiters)

    @staticmethod
    def _notify(waiters):
        def wake(future):
            if not future.done():
                future.set_result(None)

        for loop, future in waiters:
            try:
                loop.call_soon_threadsafe(wake, future)
            except RuntimeError:
                # Execution ownership has already been cleared in the worker.
                # A closed loop cannot receive a drain notification.
                pass

    async def run(self, function, *args, group: str | None = None, **kwargs):
        token = self._register(group)

        def call():
            # The executor can already be running while cancellation withdraws
            # the pending call. Never start the handler after that withdrawal.
            if not self._begin(token):
                return None
            try:
                return function(*args, **kwargs)
            finally:
                self._finish(token)

        try:
            return await asyncio.to_thread(call)
        except BaseException:
            self._withdraw_pending(token)
            raise

    async def drain(self, group: str | None = None):
        loop = asyncio.get_running_loop()
        while True:
            with self._lock:
                active = (
                    self._calls
                    if group is None
                    else any(owner == group for owner, _ in self._calls.values())
                )
                if not active:
                    return
                waiter = (loop, loop.create_future())
                self._waiters.add(waiter)
            try:
                await waiter[1]
            finally:
                with self._lock:
                    self._waiters.discard(waiter)


current_thread_tracker: ContextVar[ThreadExecutionTracker | None] = ContextVar(
    "ralf_thread_execution_tracker", default=None
)
current_thread_group: ContextVar[str | None] = ContextVar(
    "ralf_thread_execution_group", default=None
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    version: str = "1"
    effect: str = "read_only"
    requires_approval: bool = False
    cost: int = 1
    config: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.name or not self.version:
            raise ValidationError("Tool name and version must be non-empty")
        if self.effect not in {
            "read_only",
            "idempotent_write",
            "queryable_write",
            "unqueryable_write",
        }:
            raise ValidationError("Unknown tool effect category")
        credits(self.cost)
        try:
            Draft202012Validator.check_schema(self.input_schema)
        except SchemaError as exc:
            raise ValidationError("Invalid tool input Schema") from exc


@dataclass(frozen=True)
class RegisteredTool:
    spec: ToolSpec
    handler: Callable
    reconciler: Callable | None
    implementation_digest: str
    _entry_pins: tuple | None = field(default=None, repr=False, compare=False)

    def check(self):
        """Check transient executable entries without changing persisted identity."""
        if self._entry_pins is None:
            return
        try:
            current = (_entry_pin(self.handler), _entry_pin(self.reconciler))
        except ValidationError as exc:
            raise DefinitionMismatch("Original tool executable entry changed") from exc
        if not _same_entry_pin(current, self._entry_pins):
            raise DefinitionMismatch("Original tool executable entry changed")

    @property
    def manifest(self):
        self.check()
        return {**asdict(self.spec), "implementation_digest": self.implementation_digest}

    def validate(self, arguments):
        self.check()
        if not isinstance(arguments, dict) or not is_valid(arguments, self.spec.input_schema):
            raise ValidationError(f"Arguments do not match Schema for tool {self.spec.name}")

    def resolve_arguments(self, arguments):
        """Resolve typed defaults before action identity, approval and policy."""
        self.check()
        from .tool_functions import TypedFunctionHandler

        if type(self.handler) is TypedFunctionHandler:
            values = self.handler.resolve_arguments(arguments)
            # The frozen Schema declares exactly the original non-context
            # parameters. Captured defaults are already merged; live signature
            # metadata and detached descriptors must not change this check.
            if any(
                name not in values for name in json.loads(self.handler._schema_json)["properties"]
            ):
                raise ValidationError("Typed arguments omit a required callable parameter")
            return values
        self.validate(arguments)
        return copy.deepcopy(arguments)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: Callable, *, reconciler: Callable | None = None):
        if not isinstance(spec, ToolSpec):
            raise ValidationError("Register a ToolSpec")
        if spec.name in self._tools:
            raise DefinitionMismatch(f"Tool already registered: {spec.name}")
        if not callable(handler) or (reconciler is not None and not callable(reconciler)):
            raise ValidationError("Tool handlers and reconcilers must be callable")
        # Admission and later checks share static lookup; unsupported descriptors
        # fail before publishing a name, without evaluating their getters.
        entry_pins = (_entry_pin(handler), _entry_pin(reconciler))
        from .delegated_coding import registered_coding_tool

        registered_coding_tool(RegisteredTool(spec, handler, reconciler, ""))
        # Bound arguments, instance state and captured dependencies belong in the
        # integrator's explicit version/config identity, never inferred from repr
        # or serialized automatically (they may include secrets).
        canonical(asdict(spec))
        identities = [_callable_identity(function) for function in (handler, reconciler)]
        self._tools[spec.name] = RegisteredTool(
            copy.deepcopy(spec),
            handler,
            reconciler,
            digest(identities),
            entry_pins,
        )
        return handler

    def register_function(self, function, **metadata):
        """Register a keyword Python function; effect must be explicitly declared."""
        from .tool_functions import register_function

        return register_function(self, function, **metadata)

    def tool(self, **metadata):
        """Decorator returning the original callable after typed registration."""

        def decorate(function):
            self.register_function(function, **metadata)
            return function

        return decorate

    def register_many(self, entries):
        """Validate all entries before publishing any name into this registry."""
        staged = ToolRegistry()
        for spec, handler, reconciler in entries:
            if spec.name in self._tools:
                raise DefinitionMismatch(f"Tool already registered: {spec.name}")
            staged.register(spec, handler, reconciler=reconciler)
        self._tools.update(staged._tools)

    def get(self, name: str) -> RegisteredTool:
        try:
            tool = self._tools[name]
        except KeyError as exc:
            raise DefinitionMismatch(f"Tool not registered: {name}") from exc
        # frozen dataclasses do not freeze nested Schema/config dictionaries.
        # A policy or caller receives a detached descriptor, not registry state.
        return RegisteredTool(
            copy.deepcopy(tool.spec),
            tool.handler,
            tool.reconciler,
            tool.implementation_digest,
            tool._entry_pins,
        )

    def manifests(self, names):
        return {name: copy.deepcopy(self.get(name).manifest) for name in names}

    def descriptions(self, names):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.spec.name,
                    "description": tool.spec.description,
                    "parameters": copy.deepcopy(tool.spec.input_schema),
                },
            }
            for tool in (self.get(name) for name in names)
        ]


def _class_entry(owner, name):
    # Read actual MRO dictionaries, bypassing metaclass/descriptor getters.
    for base in type.__dict__["__mro__"].__get__(owner):
        namespace = type.__dict__["__dict__"].__get__(base)
        if name in namespace:
            return namespace[name]
    raise ValidationError(f"Unsupported callable descriptor for {name}")


def _direct_function_pin(function):
    if type(function) is FunctionType:
        return (function, function.__code__)
    if type(function) in {
        BuiltinFunctionType,
        MethodDescriptorType,
        ClassMethodDescriptorType,
        WrapperDescriptorType,
    }:
        return (function,)
    raise ValidationError(
        "Unsupported callable descriptor; use an explicit Python function wrapper"
    )


def _descriptor_pin(descriptor):
    # Only these built-in descriptor forms have known binding behavior. Custom
    # descriptors (including subclasses overriding __get__) need an explicit
    # ordinary wrapper, rather than running arbitrary getters during validation.
    if type(descriptor) in {staticmethod, classmethod}:
        return (descriptor, _direct_function_pin(descriptor.__func__))
    if type(descriptor) is property:
        return (descriptor, _direct_function_pin(descriptor.fget))
    return _direct_function_pin(descriptor)


def _entry_pin(function):
    # Only direct entries and code objects are retained, by identity. Never
    # serialize defaults, closures, receiver state or partial arguments.
    if function is None:
        return None
    if isinstance(function, partial):
        if _class_entry(type(function), "func") is not partial.func:
            raise ValidationError("Unsupported callable descriptor for partial.func; use a wrapper")
        return (
            function,
            _entry_pin(partial.func.__get__(function)),
            _descriptor_pin(_class_entry(type(function), "__call__")),
        )
    if type(function) is MethodType:
        return (function.__self__, _direct_function_pin(function.__func__))
    if isinstance(function, type):
        return (
            function,
            _descriptor_pin(_class_entry(type(function), "__call__")),
            _descriptor_pin(_class_entry(function, "__new__")),
            _descriptor_pin(_class_entry(function, "__init__")),
        )
    if type(function) is MethodWrapperType:
        raise ValidationError("Unsupported callable method-wrapper; use a Python function wrapper")
    if type(function) is BuiltinFunctionType:
        # This is the captured callable, just as for a captured Python method.
        # Rebinding the owner's attribute does not change this executable entry.
        return (function,)
    if type(function) in {
        FunctionType,
        MethodDescriptorType,
        ClassMethodDescriptorType,
        WrapperDescriptorType,
    }:
        return _direct_function_pin(function)
    return (function, _descriptor_pin(_class_entry(type(function), "__call__")))


def _same_entry_pin(current, original):
    if type(current) is tuple and type(original) is tuple:
        return len(current) == len(original) and all(
            _same_entry_pin(a, b) for a, b in zip(current, original, strict=True)
        )
    return current is original


def _callable_identity(function):
    from .delegated_coding import CodingToolHandler
    from .tool_functions import TypedFunctionHandler

    if type(function) is CodingToolHandler:
        return function.implementation_identity
    if type(function) is TypedFunctionHandler:
        return function.implementation_identity
    if function is None:
        return None
    if isinstance(function, partial):
        return {"kind": "partial", "function": _callable_identity(function.func)}
    if inspect.ismethod(function):
        owner = function.__self__
        owner_type = owner if inspect.isclass(owner) else type(owner)
        return {
            "kind": "bound-method",
            "owner": f"{owner_type.__module__}.{owner_type.__qualname__}",
            "function": _callable_identity(function.__func__),
        }
    target = function if hasattr(function, "__qualname__") else type(function)
    try:
        source = inspect.getsource(target)
    except (OSError, TypeError):
        source = None
    return {"module": target.__module__, "name": target.__qualname__, "source": source}


async def invoke(
    function,
    arguments: dict,
    context,
    *,
    thread_tracker: ThreadExecutionTracker | None = None,
    verify: Callable | None = None,
) -> Any:
    values = copy.deepcopy(arguments)
    if verify is not None:
        verify()
    if inspect.iscoroutinefunction(function):
        return await function(values, context)

    def call():
        # A worker may have waited in the pool while registration drifted.
        if verify is not None:
            verify()
        return function(values, context)

    # A trusted sync handler cannot block the coordinator's event loop.
    tracker = thread_tracker or current_thread_tracker.get()
    if tracker is None:
        result = await asyncio.to_thread(call)
    else:
        result = await tracker.run(call, group=context.run_id)
    if inspect.isawaitable(result):
        return await result
    return result
