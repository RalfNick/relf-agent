"""Profile-selected presentation keeps original Actions, events and ownership."""

import asyncio
import json
from contextlib import aclosing

import pytest

import relf_agent as r
from relf_agent.errors import DefinitionMismatch, ValidationError
from relf_agent.runtime_config import load_catalog

LIMITS = {
    "max_deltas": 8,
    "max_bytes": 4096,
    "max_payload_bytes": 512,
    "publish_timeout": 0.5,
}


def profile(*, config=None, enabled=True, tools=False, providers=None):
    components = {"stream_updates": {"adapter": "bounded", "config": config or {}}}
    if not enabled:
        components = {}
    if tools:
        components["tools"] = {"adapter": "fixture-progress"}
    return r.RuntimeProfile(
        "progress",
        "1",
        {} if providers is None else providers,
        components,
    )


def graph():
    return r.GraphWorkflowSpec(
        "progress", [r.GraphNode("change", tool="change")], output=r.ValueRef("change")
    )


def tool_builder(handler, *, approval=False):
    tools, registry = r.ToolRegistry(), r.ComponentRegistry()
    tools.register(
        r.ToolSpec(
            "change",
            "Report a managed operation",
            {"type": "object"},
            effect="idempotent_write" if approval else "read_only",
            requires_approval=approval,
        ),
        handler,
    )
    registry.register("tools", "fixture-progress", lambda config, context: tools)
    return r.RuntimeBuilder(registry)


def write_catalog(path, extension):
    if extension == "json":
        selected = profile(config=LIMITS, tools=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "default": {"name": "progress", "version": "1"},
                    "profiles": [
                        {
                            "name": selected.name,
                            "version": selected.version,
                            "providers": selected.providers,
                            "components": selected.components,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    else:
        path.write_text(
            """schema_version = 1
[default]
name = "progress"
version = "1"
[[profiles]]
name = "progress"
version = "1"
providers = {}
[profiles.components.tools]
adapter = "fixture-progress"
[profiles.components.stream_updates]
adapter = "bounded"
[profiles.components.stream_updates.config]
max_deltas = 8
max_bytes = 4096
max_payload_bytes = 512
publish_timeout = 0.5
""",
            encoding="utf-8",
        )


@pytest.mark.parametrize("extension", ["json", "toml"])
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_catalog_policy_drives_real_managed_tool_progress(tmp_path, extension, mode):
    path = tmp_path / ("runtime." + extension)
    write_catalog(path, extension)
    selected = load_catalog(path).default
    assert selected.identity == profile(config=LIMITS, tools=True).identity
    calls, reports = [], []

    async def change(arguments, context):
        reports.append(await r.emit_tool_delta({"message": "working"}))
        calls.append(context.effect_key)
        reports.append(await r.emit_tool_delta({"message": "done"}))
        return {"completed": True}

    async def run():
        builder = tool_builder(change)
        database = tmp_path / "runs.sqlite"
        built = (
            builder.build(selected, database)
            if mode == "sync"
            else await builder.abuild(selected, database)
        )
        async with r.Runtime(built, owned=True) as runtime:
            handle = await runtime.create_agent(graph()).submit({}, command_id="same")
            assert (await handle.wait(wait_timeout=2)).snapshot.result == {"completed": True}
            async with aclosing(handle.stream_updates(follow=False)) as updates:
                rows = [row async for row in updates]
            assert [row.data for row in rows if row.kind == "tool_delta"] == [
                {"message": "working"},
                {"message": "done"},
            ]
            assert not any(row.kind == "model_delta" for row in rows)
            assert all(not row.authoritative for row in rows if row.kind == "tool_delta")
            (end,) = [row for row in rows if row.kind == "tool_end"]
            assert end.authoritative and end.data["stream_end"]["observation"]["published"] == 2
            manifest = (await handle.diagnostics()).manifest
            assert manifest["stream_updates"] == r.StreamUpdatePolicy(**LIMITS).identity
            assert [row.envelope.event for row in rows] == await handle.events()
        assert calls and len(calls) == 1 and reports == [True, True]

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_policy_only_does_not_convert_plain_model_to_stream(tmp_path, mode):
    async def run():
        selected = profile(providers={"default": {"adapter": "offline-echo"}})
        builder = r.RuntimeBuilder()
        built = (
            builder.build(selected, tmp_path / "model.sqlite")
            if mode == "sync"
            else await builder.abuild(selected, tmp_path / "model.sqlite")
        )
        async with r.Runtime(built, owned=True) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer")).submit(
                "hello", command_id="same"
            )
            assert (await handle.wait(wait_timeout=2)).snapshot.result == {
                "echo": "hello",
                "label": "offline",
            }
            async with aclosing(handle.stream_updates()) as updates:
                rows = [row async for row in updates]
            assert not any(row.kind == "model_delta" for row in rows)
            assert any(row.kind == "model_end" and row.authoritative for row in rows)

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_policy_reopen_preserves_approval_command_receipt_and_delivered_cursor(tmp_path, mode):
    calls, reports = [], []

    async def change(arguments, context):
        calls.append(context.effect_key)
        reports.append(await r.emit_tool_delta({"message": "written"}))
        return {"completed": True}

    async def run():
        builder, selected = tool_builder(change, approval=True), profile(config=LIMITS, tools=True)
        database, spec = tmp_path / "restart.sqlite", graph()

        async def open_built(chosen=selected):
            return (
                builder.build(chosen, database)
                if mode == "sync"
                else await builder.abuild(chosen, database)
            )

        async with r.Runtime(await open_built(), owned=True) as runtime:
            handle = await runtime.create_agent(spec).submit({}, command_id="same")
            paused = await handle.wait(wait_timeout=2)
            assert paused.snapshot.state == "waiting_approval" and not calls
            ref, action = handle.ref, paused.snapshot.pending[0]
            async with aclosing(handle.stream_updates(follow=False)) as updates:
                prefix = [row async for row in updates]
                cursor = r.EventCursor.from_token(updates.cursor.token)

        changed = profile(config={**LIMITS, "max_deltas": 9}, tools=True)
        async with await open_built(changed) as wrong:
            with pytest.raises(DefinitionMismatch):
                await wrong.drive(ref.run_id)
            assert wrong.status(ref.run_id).state == "waiting_approval" and not calls

        async with r.Runtime(await open_built(), owned=True) as runtime:
            handle = runtime.attach(ref)
            receipt = await handle.approve(
                action["action_id"], action["digest"], command_id="approve"
            )
            assert (await handle.wait(wait_timeout=2, terminal_only=True)).snapshot.result == {
                "completed": True
            }
            original_events = await handle.events()

        async with r.Runtime(await open_built(), owned=True) as runtime:
            handle = await runtime.create_agent(spec).submit({}, command_id="same")
            assert handle.ref == ref
            assert (
                await handle.approve(action["action_id"], action["digest"], command_id="approve")
                == receipt
            )
            assert (await handle.wait(wait_timeout=2, terminal_only=True)).snapshot.result == {
                "completed": True
            }
            async with aclosing(handle.stream_updates(after=cursor, follow=False)) as updates:
                suffix = [row async for row in updates]
            assert [row.envelope.event for row in prefix + suffix] == original_events
            assert await handle.events() == original_events
            assert [row.data for row in suffix if row.kind == "tool_delta"] == [
                {"message": "written"}
            ]
        assert len(calls) == 1 and reports == [True]

    asyncio.run(run())


def test_observer_cancel_does_not_cancel_configured_managed_tool(tmp_path):
    async def run():
        entered, release, calls = asyncio.Event(), asyncio.Event(), []

        async def change(arguments, context):
            assert await r.emit_tool_delta({"message": "started"})
            entered.set()
            await release.wait()
            calls.append(context.effect_key)
            assert await r.emit_tool_delta({"message": "finished"})
            return {"completed": True}

        builder = tool_builder(change)
        async with await r.Runtime.afrom_profile(
            profile(tools=True), tmp_path / "observe.sqlite", builder=builder
        ) as runtime:
            handle = await runtime.create_agent(graph()).submit({}, command_id="same")
            try:
                await asyncio.wait_for(entered.wait(), 2)
                async with aclosing(handle.stream_updates(follow=False)) as updates:
                    prefix = [row async for row in updates]
                    cursor = updates.cursor
                assert [row.data for row in prefix if row.kind == "tool_delta"] == [
                    {"message": "started"}
                ]
                observer = handle.stream_updates(after=cursor, poll_interval=0.01)
                reader = asyncio.create_task(anext(observer))
                await asyncio.sleep(0.02)
                reader.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await reader
                await observer.aclose()
                assert (await handle.status()).state == "running" and not calls
            finally:
                release.set()
            assert (await handle.wait(wait_timeout=2)).snapshot.result == {"completed": True}
            async with aclosing(handle.stream_updates(after=cursor)) as updates:
                suffix = [row async for row in updates]
            assert [row.data for row in suffix if row.kind == "tool_delta"] == [
                {"message": "finished"}
            ]
        assert len(calls) == 1

    asyncio.run(run())


def test_configured_delta_limit_keeps_original_tool_result(tmp_path):
    reports = []

    async def change(arguments, context):
        for index in range(3):
            reports.append(await r.emit_tool_delta({"index": index}))
        return {"completed": True}

    async def run():
        selected = profile(config={"max_deltas": 1}, tools=True)
        async with await r.Runtime.afrom_profile(
            selected, tmp_path / "bounded.sqlite", builder=tool_builder(change)
        ) as runtime:
            handle = await runtime.create_agent(graph()).submit({}, command_id="same")
            assert (await handle.wait(wait_timeout=2)).snapshot.result == {"completed": True}
            async with aclosing(handle.stream_updates()) as updates:
                rows = [row async for row in updates]
            assert [row.data for row in rows if row.kind == "tool_delta"] == [{"index": 0}]
            assert [row.data for row in rows if row.kind == "gap"] == [{"reason": "capacity"}]
            (end,) = [row for row in rows if row.kind == "tool_end"]
            assert end.data["stream_end"]["observation"] == {
                "published": 1,
                "truncated": True,
                "reason": "capacity",
            }
        assert reports == [True, False, False]

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_omitted_component_retains_original_manifest_and_emits_no_updates(tmp_path, mode):
    reports = []

    async def change(arguments, context):
        reports.append(await r.emit_tool_delta({"message": "hidden"}))
        return {"completed": True}

    async def run():
        builder, selected, spec = tool_builder(change), profile(enabled=False, tools=True), graph()
        path = tmp_path / "default.sqlite"
        built = (
            builder.build(selected, path)
            if mode == "sync"
            else await builder.abuild(selected, path)
        )
        async with built:
            handle = built.submit(spec, {}, command_id="same")
            before = built.diagnostics(handle.run_id).manifest
            assert "stream_updates" not in before
            assert (await built.drive(handle.run_id)).result == {"completed": True}
            assert not any(event.kind == "agent_update" for event in built.events(handle.run_id))
            tools = built.tools
        with r.LocalEngine(
            r.SQLiteStore(path), providers={}, tools=tools, runtime_profile=selected.identity
        ) as original:
            assert original.diagnostics(handle.run_id).manifest == before
            assert original.submit(spec, {}, command_id="same") == handle
            assert (await original.drive(handle.run_id)).result == {"completed": True}
        assert reports == [False]

    asyncio.run(run())


BAD_CONFIGS = [
    {"unknown": 1},
    {"version": 1},
    *({"max_deltas": value} for value in (0, 1025, True, 1.5, "8", None)),
    *({"max_bytes": value} for value in (255, 1048577, True, 256.0)),
    *({"max_payload_bytes": value} for value in (255, 65537, True, 256.0)),
    {"max_bytes": 256, "max_payload_bytes": 512},
    *({"publish_timeout": value} for value in (0, -1, 2.01, True, "1", None, 10**1000)),
]


@pytest.mark.parametrize("config", BAD_CONFIGS)
@pytest.mark.parametrize("mode", ["sync", "async", "temporal"])
def test_invalid_policy_refuses_before_any_resource_allocation(tmp_path, config, mode):
    registry, allocations = r.ComponentRegistry(), []

    def provider(options, context):
        allocations.append("provider")
        pytest.fail("Invalid presentation settings must fail before factories")

    def store(path):
        allocations.append("store")
        pytest.fail("Invalid presentation settings must fail before execution allocation")

    registry.register("provider", "fixture-unallocated", provider)
    chosen = profile(config=config, providers={"default": {"adapter": "fixture-unallocated"}})

    async def run():
        with pytest.raises(ValidationError):
            if mode == "temporal":
                temporal = r.TemporalProfile(
                    chosen.name, chosen.version, chosen.providers, chosen.components
                )
                await r.TemporalRuntimeBuilder(registry, base_dir=tmp_path).abuild(temporal)
            else:
                builder = r.RuntimeBuilder(registry, store_factory=store)
                if mode == "sync":
                    builder.build(chosen, tmp_path / "must-not-exist.sqlite")
                else:
                    await builder.abuild(chosen, tmp_path / "must-not-exist.sqlite")
        assert allocations == [] and not any(tmp_path.iterdir())

    asyncio.run(run())


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_policy_is_rejected_without_factories(timeout):
    with pytest.raises(ValidationError):
        profile(config={"publish_timeout": timeout})


@pytest.mark.parametrize("enabled", [False, True])
def test_temporal_offline_assembly_preserves_same_original_manifest_policy(tmp_path, enabled):
    from relf_agent.temporal_activities import TemporalRuntime

    async def run():
        chosen = profile(
            config=LIMITS,
            enabled=enabled,
            providers={"default": {"adapter": "offline-echo"}},
        )
        temporal = r.TemporalProfile(
            chosen.name, chosen.version, chosen.providers, chosen.components
        )
        assembly = await r.TemporalRuntimeBuilder(base_dir=tmp_path).abuild(temporal)
        try:
            assert ("stream_updates" in assembly.release) is enabled
            if enabled:
                assert assembly.release["stream_updates"] == r.StreamUpdatePolicy(**LIMITS).identity
            original = TemporalRuntime(
                providers=assembly._runtime.providers,
                tools=r.ToolRegistry(),
                runtime_profile=temporal.identity,
                stream_updates=r.StreamUpdatePolicy(**LIMITS) if enabled else None,
            )
            assert assembly.release == original.orchestration_release
            assert assembly._context._resources == []
            assert not any(tmp_path.iterdir())
        finally:
            await assembly.aclose()
        assert not any(tmp_path.iterdir())

    asyncio.run(run())
