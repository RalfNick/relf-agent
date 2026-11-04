"""Observation, business cancellation and real executor exit stay distinct."""

import asyncio

import pytest

import relf_agent as r
from relf_agent.coordinator import FileCoordinator
from relf_agent.errors import CoordinatorBusy, ValidationError


class BlockingNode:
    identity = {"kind": "blocking-async-node", "version": "1"}

    def __init__(self):
        self.entered = asyncio.Event()
        self.finish = asyncio.Event()
        self.swallowed = asyncio.Event()
        self.exited = asyncio.Event()
        self.task = None
        self.calls = []

    async def execute(self, input, config, context):
        self.task = asyncio.current_task()
        self.calls.append((input, config, context.effect_key))
        self.entered.set()
        try:
            await self.finish.wait()
        except asyncio.CancelledError:
            self.swallowed.set()
            await self.finish.wait()
        self.exited.set()
        return input


def nodes(component):
    registry = r.NodeExecutorRegistry()
    registry.register(
        r.NodeExecutorSpec("business", "Blocking business operation", effect="read_only", cost=2),
        component,
    )
    return registry


def flow(parallel):
    return r.GraphWorkflowSpec(
        "cancellation",
        [
            r.GraphNode("first", executor="business", config={"fixed": True}),
            r.GraphNode(
                "successor",
                executor="business",
                depends_on=("first",),
                input=r.Literal("forbidden"),
            ),
        ],
        output=r.ValueRef("successor"),
        max_concurrency=2 if parallel else 1,
    )


def assert_coordinator_owned(path):
    contender = FileCoordinator(str(path) + ".coordinator")
    with pytest.raises(CoordinatorBusy):
        contender.acquire()


def assert_coordinator_released(path):
    contender = FileCoordinator(str(path) + ".coordinator")
    contender.acquire()
    contender.release()


@pytest.mark.parametrize("parallel", [False, True])
def test_cancelled_drive_observation_keeps_actual_node_owned_until_receipt(tmp_path, parallel):
    async def exercise():
        component = BlockingNode()
        path = tmp_path / "observation.sqlite"
        engine = r.LocalEngine(
            r.SQLiteStore(path),
            providers={},
            tools=r.ToolRegistry(),
            workflow_executors=nodes(component),
        )
        handle = engine.submit(flow(parallel), [None, 1], command_id="submit", budget=8)
        observer = asyncio.create_task(engine.drive(handle.run_id))
        owned = None
        try:
            await asyncio.wait_for(component.entered.wait(), 5)
            before = engine.store.run(handle.run_id)["actions"][0]
            owned = engine._inflight[handle.run_id]
            observer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await observer
            assert not component.exited.is_set() and not component.swallowed.is_set()
            with pytest.raises(CoordinatorBusy):
                await engine.drive(handle.run_id)
            with pytest.raises(ValidationError):
                engine.close()
            assert_coordinator_owned(path)
            assert engine.diagnostics(handle.run_id).budget == {"limit": 8, "held": 2, "spent": 0}
            component.finish.set()
            await asyncio.wait_for(asyncio.shield(owned), 5)
            done = await engine.drive(handle.run_id)
            assert done.state == "cancelled" and component.exited.is_set()
            assert component.calls == [([None, 1], {"fixed": True}, before["effect_key"])]
            after = engine.store.run(handle.run_id)
            assert len(after["actions"]) == 1
            action = after["actions"][0]
            for key in ("id", "effect_key", "digest"):
                assert action[key] == before[key]
            assert action["status"] == "completed" and action["result"] == [None, 1]
            assert action["effect_observation"]["result"] == [None, 1]
            assert engine.diagnostics(handle.run_id).budget == {"limit": 8, "held": 0, "spent": 2}
        finally:
            component.finish.set()
            await asyncio.gather(observer, return_exceptions=True)
            if owned is not None:
                await asyncio.gather(owned, return_exceptions=True)
            engine.close()
        assert_coordinator_released(path)

    asyncio.run(exercise())


@pytest.mark.parametrize("parallel", [False, True])
def test_executor_swallowing_real_task_cancel_cannot_release_or_schedule_successor(
    tmp_path, parallel
):
    async def exercise():
        component = BlockingNode()
        path = tmp_path / "swallowed.sqlite"
        engine = r.LocalEngine(
            r.SQLiteStore(path),
            providers={},
            tools=r.ToolRegistry(),
            workflow_executors=nodes(component),
        )
        handle = engine.submit(flow(parallel), None, command_id="submit", budget=8)
        observer = asyncio.create_task(engine.drive(handle.run_id))
        try:
            await asyncio.wait_for(component.entered.wait(), 5)
            component.task.cancel()
            await asyncio.wait_for(component.swallowed.wait(), 5)
            receipt = engine.cancel(handle.run_id, command_id="cancel")
            assert engine.cancel(handle.run_id, command_id="cancel") == receipt
            assert not component.exited.is_set() and not observer.done()
            with pytest.raises(ValidationError):
                engine.close()
            assert_coordinator_owned(path)
            component.finish.set()
            done = await asyncio.wait_for(asyncio.shield(observer), 5)
            assert done.state == "cancelled" and component.exited.is_set()
            action = engine.store.run(handle.run_id)["actions"][0]
            assert action["status"] == "completed" and action["result"] is None
            assert component.calls == [(None, {"fixed": True}, action["effect_key"])]
            assert len(engine.store.run(handle.run_id)["actions"]) == 1
            assert engine.diagnostics(handle.run_id).budget == {"limit": 8, "held": 0, "spent": 2}
        finally:
            component.finish.set()
            await asyncio.gather(observer, return_exceptions=True)
            engine.close()
        assert_coordinator_released(path)

    asyncio.run(exercise())


def test_owned_node_client_close_retries_after_actual_exit_without_reexecuting(tmp_path):
    async def exercise():
        events = []

        class Client(BlockingNode):
            def __init__(self):
                super().__init__()
                self.closes = 0
                self.closed = False

            async def aclose(self):
                assert self.exited.is_set()
                self.closes += 1
                events.append(f"close-{self.closes}")
                if self.closes == 1:
                    raise ConnectionError("client cleanup incomplete")
                self.closed = True

        component = Client()

        async def factory(config, context):
            assert config == {}
            context.own_async(component)
            return nodes(component)

        components = r.ComponentRegistry()
        components.register_async("workflow_executors", "owned-retry", factory)
        profile = r.RuntimeProfile(
            "owned-retry", "1", {}, {"workflow_executors": {"adapter": "owned-retry"}}
        )
        path = tmp_path / "close-retry.sqlite"
        runtime = await r.RuntimeBuilder(components).abuild(profile, path)
        spec = r.GraphWorkflowSpec(
            "owned", [r.GraphNode("n", executor="business")], output=r.ValueRef("n")
        )
        handle = runtime.submit(spec, [1, None], command_id="submit", budget=2)
        observer = asyncio.create_task(runtime.drive(handle.run_id))
        try:
            await asyncio.wait_for(component.entered.wait(), 5)
            with pytest.raises(ValidationError):
                await runtime.aclose()
            assert component.closes == 0 and not component.closed
            assert_coordinator_owned(path)
            component.finish.set()
            done = await asyncio.wait_for(asyncio.shield(observer), 5)
            assert done.state == "succeeded" and done.result == [1, None]
            with pytest.raises(ConnectionError, match="cleanup incomplete"):
                await runtime.aclose()
            assert component.closes == 1 and not component.closed
            with pytest.raises(ValidationError):
                runtime.status(handle.run_id)
            await runtime.aclose()
            await runtime.aclose()
            assert component.closed and events == ["close-1", "close-2"]
            assert len(component.calls) == 1
        finally:
            component.finish.set()
            await asyncio.gather(observer, return_exceptions=True)
            await runtime.aclose()
        assert_coordinator_released(path)
        with r.SQLiteStore(path, readonly=True) as store:
            action = store.run(handle.run_id)["actions"][0]
            assert action["status"] == "completed" and action["result"] == [1, None]
            assert store.budget(handle.run_id) == {"limit": 2, "held": 0, "spent": 2}

    asyncio.run(exercise())


def test_parallel_failure_waits_for_actual_sibling_exit_and_keeps_its_receipt(tmp_path):
    async def exercise():
        entered, failed, finish, exited = (asyncio.Event() for _ in range(4))
        calls = []

        class Store(r.SQLiteStore):
            def emit(self, run_id, kind, data=None):
                super().emit(run_id, kind, data)
                if kind == "run_failed":
                    failed.set()

        class Component:
            identity = {"kind": "failing-parallel-node", "version": "1"}

            async def execute(self, input, config, context):
                calls.append(input)
                if input == "bad":
                    await entered.wait()
                    return "invalid-output"
                entered.set()
                await finish.wait()
                exited.set()
                return input

        path = tmp_path / "parallel-failure.sqlite"
        engine = r.LocalEngine(
            Store(path), providers={}, tools=r.ToolRegistry(), workflow_executors=nodes(Component())
        )
        spec = r.GraphWorkflowSpec(
            "failure",
            [
                r.GraphNode(
                    "bad",
                    executor="business",
                    input=r.Literal("bad"),
                    output_schema={"type": "integer"},
                ),
                r.GraphNode("slow", executor="business", input=r.Literal(None)),
                r.GraphNode(
                    "next", executor="business", depends_on=("slow",), input=r.Literal("forbidden")
                ),
            ],
            max_concurrency=2,
        )
        handle = engine.submit(spec, {}, command_id="submit", budget=6)
        observer = asyncio.create_task(engine.drive(handle.run_id))
        try:
            await asyncio.wait_for(failed.wait(), 5)
            assert not exited.is_set() and not observer.done()
            with pytest.raises(ValidationError):
                engine.close()
            assert_coordinator_owned(path)
            finish.set()
            done = await asyncio.wait_for(asyncio.shield(observer), 5)
            assert done.state == "failed" and done.error["code"] == "validation_error"
            assert exited.is_set() and calls == ["bad", None]
            actions = engine.store.run(handle.run_id)["actions"]
            assert len(actions) == 2 and all(action["status"] == "completed" for action in actions)
            assert [action["result"] for action in actions] == ["invalid-output", None]
            assert engine.diagnostics(handle.run_id).budget == {"limit": 6, "held": 0, "spent": 4}
        finally:
            finish.set()
            await asyncio.gather(observer, return_exceptions=True)
            engine.close()
        assert_coordinator_released(path)

    asyncio.run(exercise())
