"""Public async nodes share the original Local Action and Workflow authority."""

import asyncio
import copy

import pytest

import relf_agent as r
from relf_agent.errors import AuthorizationDenied, DefinitionMismatch, ValidationError


def registry(component, *, effect="read_only", approval=False, **options):
    assert hasattr(r, "NodeExecutorRegistry"), "Missing managed NodeExecutor registry"
    result = r.NodeExecutorRegistry()
    result.register(
        r.NodeExecutorSpec(
            "business", "Business node", effect=effect, requires_approval=approval, **options
        ),
        component,
    )
    return result


def engine(path, nodes, *, tools=None, **options):
    store = r.SQLiteStore(path)
    try:
        return r.LocalEngine(
            store,
            providers={},
            tools=r.ToolRegistry() if tools is None else tools,
            workflow_executors=nodes,
            **options,
        )
    except BaseException:
        store.close()
        raise


def graph(**options):
    return r.GraphWorkflowSpec(
        "async-node",
        [r.GraphNode("business", executor="business", **options)],
        output=r.ValueRef("business"),
    )


class Echo:
    identity = {"kind": "node-echo", "version": "1"}

    def __init__(self):
        self.calls = []

    async def execute(self, input, config, context):
        await asyncio.sleep(0)
        self.calls.append((copy.deepcopy(input), copy.deepcopy(config), context.effect_key))
        return input


@pytest.mark.parametrize("value", [None, False, 0, "text", [1, "中"], {"number": 3}])
def test_full_json_and_config_reach_structural_executor_without_model(tmp_path, value):
    component = Echo()
    with engine(tmp_path / "run.sqlite", registry(component)) as runtime:
        handle = runtime.submit(graph(config={"mode": "full"}), value, command_id="submit")
        done = asyncio.run(runtime.drive(handle.run_id))
        assert done.state == "succeeded" and done.result == value
        assert component.calls[0][:2] == (value, {"mode": "full"})
        run = runtime.store.run(handle.run_id)
        assert len(run["actions"]) == 1 and run["actions"][0]["kind"] == "tool"
        assert run["actions"][0]["arguments"] == {"input": value, "config": {"mode": "full"}}
        assert run["plan"]["schema_version"] == 2
        assert runtime.diagnostics(handle.run_id).budget["spent"] == 1
        assert runtime.tools.descriptions([]) == []


def test_approval_and_original_receipts_survive_reopen(tmp_path):
    component, path = Echo(), tmp_path / "run.sqlite"

    def nodes():
        return registry(component, effect="unqueryable_write", approval=True, cost=2)

    with engine(path, nodes()) as runtime:
        handle = runtime.submit(graph(config={"target": "approved"}), [1, 2], command_id="submit")
        paused = asyncio.run(runtime.drive(handle.run_id))
        assert paused.state == "waiting_approval" and not component.calls
        pending = paused.pending[0]
    with engine(path, nodes()) as runtime:
        receipt = runtime.approve(
            handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
        )
        assert asyncio.run(runtime.drive(handle.run_id)).result == [1, 2]
    with engine(path, nodes()) as runtime:
        assert (
            runtime.submit(graph(config={"target": "approved"}), [1, 2], command_id="submit")
            == handle
        )
        assert (
            runtime.approve(
                handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
            )
            == receipt
        )
        before = runtime.events(handle.run_id)
        assert asyncio.run(runtime.drive(handle.run_id)).state == "succeeded"
        assert runtime.events(handle.run_id) == before
        assert runtime.diagnostics(handle.run_id).budget["spent"] == 2
    assert len(component.calls) == 1


@pytest.mark.parametrize("reason", ["input", "config", "budget", "authorization"])
def test_failed_admission_never_executes_node(tmp_path, reason):
    component = Echo()

    def policy(scope, spec, arguments):
        if reason == "authorization":
            assert spec.name == "__relf_node__:business"
            assert arguments == {"input": 3, "config": {}}
            raise AuthorizationDenied("denied")

    nodes = registry(
        component,
        input_schema={"type": "integer"},
        config_schema={"type": "object", "maxProperties": 0},
    )
    with engine(tmp_path / "run.sqlite", nodes, policy=policy) as runtime:
        handle = runtime.submit(
            graph(config={"bad": 1} if reason == "config" else {}),
            "bad" if reason == "input" else 3,
            command_id="submit",
            budget=0 if reason == "budget" else 10,
        )
        assert asyncio.run(runtime.drive(handle.run_id)).state == "failed"
    assert component.calls == []


def test_output_schema_failure_retains_completed_effect_and_never_reexecutes(tmp_path):
    component = Echo()
    with engine(
        tmp_path / "run.sqlite", registry(component, output_schema={"type": "integer"})
    ) as runtime:
        handle = runtime.submit(graph(), "invalid-output", command_id="submit")
        done = asyncio.run(runtime.drive(handle.run_id))
        assert done.state == "failed" and done.error["code"] == "validation_error"
        action = runtime.store.run(handle.run_id)["actions"][0]
        assert action["status"] == "completed" and action["result"] == "invalid-output"
        assert "effect_observation" in action
        assert runtime.diagnostics(handle.run_id).budget["spent"] == 1
        assert asyncio.run(runtime.drive(handle.run_id)).state == "failed"
    assert len(component.calls) == 1


def test_queryable_unknown_result_null_uses_original_effect_observation(tmp_path):
    class Query:
        identity = {"kind": "query-null", "version": "1"}

        def __init__(self):
            self.calls = self.queries = 0

        async def execute(self, input, config, context):
            self.calls += 1
            raise RuntimeError("lost response")

        async def reconcile(self, input, config, context):
            self.queries += 1
            return r.EffectObservation(None)

    component = Query()
    with engine(tmp_path / "run.sqlite", registry(component, effect="queryable_write")) as runtime:
        handle = runtime.submit(graph(), None, command_id="submit")
        assert asyncio.run(runtime.drive(handle.run_id)).state == "waiting_reconciliation"
        done = asyncio.run(runtime.drive(handle.run_id))
        assert done.state == "succeeded" and done.result is None
    assert (component.calls, component.queries) == (1, 1)


def test_unqueryable_write_requires_original_manual_confirmation(tmp_path):
    class Lost(Echo):
        async def execute(self, input, config, context):
            self.calls.append(context.effect_key)
            raise RuntimeError("lost")

    component = Lost()
    with engine(
        tmp_path / "run.sqlite", registry(component, effect="unqueryable_write")
    ) as runtime:
        handle = runtime.submit(graph(), [1], command_id="submit")
        assert asyncio.run(runtime.drive(handle.run_id)).state == "waiting_reconciliation"
        assert asyncio.run(runtime.drive(handle.run_id)).state == "waiting_reconciliation"
        action = runtime.store.run(handle.run_id)["actions"][0]
        runtime.reconcile(handle.run_id, action["id"], {"verified": True}, command_id="confirm")
        assert asyncio.run(runtime.drive(handle.run_id)).result == {"verified": True}
    assert len(component.calls) == 1


def test_parallel_nodes_share_parent_authority_and_nested_input_maps(tmp_path):
    class Barrier(Echo):
        async def execute(self, input, config, context):
            self.calls.append((input, context.run_id))
            if len(self.calls) == 2:
                ready.set()
            await ready.wait()
            return input

    async def run():
        nonlocal ready
        ready = asyncio.Event()
        component = Barrier()
        flow = r.GraphWorkflowSpec(
            "parallel",
            [
                r.GraphNode(
                    "left", executor="business", input=r.InputMap({"n": r.ValueRef(path=("n",))})
                ),
                r.GraphNode("right", executor="business", input=r.Literal([2])),
                r.GraphNode(
                    "join",
                    transform="identity",
                    depends_on=("left", "right"),
                    input=r.InputMap({"left": r.ValueRef("left"), "right": r.ValueRef("right")}),
                ),
            ],
            output=r.ValueRef("join"),
            max_concurrency=2,
        )
        with engine(tmp_path / "run.sqlite", registry(component)) as runtime:
            handle = runtime.submit(flow, {"n": 1}, command_id="submit")
            done = await asyncio.wait_for(runtime.drive(handle.run_id), 3)
            assert done.state == "succeeded" and done.result == {"left": {"n": 1}, "right": [2]}
            assert {run_id for _, run_id in component.calls} == {handle.run_id}
            assert runtime.store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1

    ready = None
    asyncio.run(run())


def test_custom_tool_executor_only_receives_public_tools(tmp_path):
    tools = r.ToolRegistry()
    tools.register(r.ToolSpec("public", "Public", {"type": "object"}), lambda args, ctx: args)

    class Custom:
        identity = {"kind": "custom-tools", "version": "1"}

        def __init__(self):
            self.calls = []
            self.delegate = r.PythonToolExecutor(tools)

        async def execute(self, envelope):
            self.calls.append(envelope.tool_name)
            return await self.delegate.execute(envelope)

        async def reconcile(self, envelope):
            return await self.delegate.reconcile(envelope)

    custom, component = Custom(), Echo()
    flow = r.GraphWorkflowSpec(
        "mixed",
        [
            r.GraphNode("node", executor="business"),
            r.GraphNode(
                "tool",
                tool="public",
                depends_on=("node",),
                input=r.InputMap({"n": r.ValueRef("node")}),
            ),
        ],
        output=r.ValueRef("tool"),
    )
    with engine(
        tmp_path / "run.sqlite", registry(component), tools=tools, tool_executor=custom
    ) as runtime:
        handle = runtime.submit(flow, 3, command_id="submit")
        assert asyncio.run(runtime.drive(handle.run_id)).result == {"n": 3}
    assert custom.calls == ["public"] and len(component.calls) == 1


def test_private_node_name_cannot_be_declared_as_an_agent_tool(tmp_path):
    component = Echo()
    with engine(tmp_path / "run.sqlite", registry(component)) as runtime:
        with pytest.raises(DefinitionMismatch):
            runtime.submit(
                r.AgentSpec("bad", "Run", ("__relf_node__:business",)), "q", command_id="bad"
            )
        assert runtime.store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
    assert component.calls == []


def test_cancel_does_not_schedule_successor_or_release_active_executor(tmp_path):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        class Wait(Echo):
            async def execute(self, input, config, context):
                self.calls.append(input)
                entered.set()
                await release.wait()
                return input

        component = Wait()
        runtime = engine(tmp_path / "run.sqlite", registry(component))
        flow = r.GraphWorkflowSpec(
            "cancel",
            [
                r.GraphNode("first", executor="business"),
                r.GraphNode(
                    "next", executor="business", depends_on=("first",), input=r.Literal(99)
                ),
            ],
        )
        handle = runtime.submit(flow, 1, command_id="submit")
        task = asyncio.create_task(runtime.drive(handle.run_id))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            runtime.cancel(handle.run_id, command_id="cancel")
            with pytest.raises(ValidationError):
                runtime.close()
            release.set()
            assert (await task).state == "cancelled"
            action = runtime.store.run(handle.run_id)["actions"][0]
            assert action["status"] == "completed" and action["result"] == 1
            assert component.calls == [1]
        finally:
            release.set()
            await task
            runtime.close()

    asyncio.run(run())


@pytest.mark.parametrize("concurrency", [1, 2])
def test_bound_mixed_graph_keeps_node_private_and_agent_capabilities(tmp_path, concurrency):
    class Provider:
        identity = {"kind": "private-model-observer", "version": "1"}

        async def complete(self, messages, tools):
            assert tools == []
            return r.ModelResponse("answer")

    component = Echo()
    flow = r.GraphWorkflowSpec(
        "bound",
        [
            r.GraphNode("node", executor="business"),
            r.GraphNode("agent", agent=r.AgentSpec("answer", "Answer")),
        ],
        max_concurrency=concurrency,
    )
    wrapped = r.BoundDefinition(flow, {"graph/nodes/agent": r.AgentBindingDescriptor()})
    with r.LocalEngine(
        r.SQLiteStore(tmp_path / "run.sqlite"),
        providers={"default": Provider()},
        tools=r.ToolRegistry(),
        workflow_executors=registry(component),
    ) as runtime:
        handle = runtime.submit(wrapped, [1, None], command_id="submit")
        done = asyncio.run(runtime.drive(handle.run_id))
        assert done.state == "succeeded" and done.result == {"node": [1, None], "agent": "answer"}
        actions = runtime.store.run(handle.run_id)["actions"]
        assert len([a for a in actions if a["kind"] == "tool"]) == 1
    assert len(component.calls) == 1


@pytest.mark.parametrize("kind", ["team", "dynamic"])
def test_nested_member_graph_uses_same_registry_and_original_child_runs(tmp_path, kind):
    component = Echo()
    flow = graph()
    outer = (
        r.TeamSpec("outer", {"member": flow})
        if kind == "team"
        else r.DynamicWorkflowSpec("outer", {"member": flow})
    )
    with engine(tmp_path / "run.sqlite", registry(component)) as runtime:
        handle = runtime.submit(outer, [7], command_id="submit")
        done = asyncio.run(runtime.drive(handle.run_id))
        assert done.state == "succeeded", done.error
        assert len(component.calls) == 1
        assert component.calls[0][0]["task"] == [7]
        before = runtime.events(handle.run_id)
        assert asyncio.run(runtime.drive(handle.run_id)).result == done.result
        assert runtime.events(handle.run_id) == before and len(component.calls) == 1


def test_unused_registration_drift_does_not_change_selected_release(tmp_path):
    component, extra = Echo(), Echo()
    nodes = registry(component)
    with engine(tmp_path / "run.sqlite", nodes) as runtime:
        first = runtime.submit(graph(), 1, command_id="first")
        selected = runtime.diagnostics(first.run_id).manifest
        nodes.register(r.NodeExecutorSpec("unused", "Unused", effect="read_only"), extra)
        extra.identity = {"kind": "changed-unused"}
        second = runtime.submit(graph(), 1, command_id="second")
        assert runtime.diagnostics(second.run_id).manifest == selected
        assert asyncio.run(runtime.drive(first.run_id)).result == 1
        assert asyncio.run(runtime.drive(second.run_id)).result == 1
    assert extra.calls == []
