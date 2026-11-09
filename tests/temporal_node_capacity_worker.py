"""Actual node peer and Workflow-only process for capacity recovery evidence."""

import asyncio
import copy
import json
import os
from pathlib import Path

import relf_agent as r
from relf_agent.temporal import build_temporal_worker
from relf_agent.temporal_activities import TemporalRuntime

from .temporal_workflow_nodes_worker import audit


class CapacityNode:
    def __init__(self, root, mode):
        self.root, self.mode = Path(root), mode

    @property
    def identity(self):
        return {
            "kind": "actual-node-capacity-peer",
            "version": "1",
            "root": str(self.root),
            "mode": self.mode,
        }

    async def execute(self, input, config, context):
        audit(
            self.root,
            "execute",
            action_id=context.action_id,
            effect_key=context.effect_key,
            slot=config["slot"],
            input=input,
        )
        if config.get("hold"):
            (self.root / ("entered-" + config["slot"])).touch()
            while not (self.root / "release-handler").exists():  # noqa: ASYNC110 -- actual peer fence
                try:
                    await asyncio.sleep(0.02)
                except asyncio.CancelledError:
                    audit(self.root, "cancel-observed", slot=config["slot"])
        audit(
            self.root,
            "ended",
            action_id=context.action_id,
            effect_key=context.effect_key,
            slot=config["slot"],
        )
        return copy.deepcopy(input)


class AcknowledgementRuntime(TemporalRuntime):
    """Delay forwarding the real original on_end callback; never supply proof."""

    async def execute_tool(self, request, **options):
        original = options.get("on_end")

        async def ended(proof):
            audit(self.fixture_root, "ack-entered", action_id=proof["action_id"])
            (self.fixture_root / "ack-entered").touch()
            while not (self.fixture_root / "release-ack").exists():  # noqa: ASYNC110 -- ACK fault fence
                await asyncio.sleep(0.02)
            await original(proof)
            audit(self.fixture_root, "ack-forwarded", action_id=proof["action_id"])

        return await super().execute_tool(request, **{**options, "on_end": ended})


def make_runtime(root, mode="hold"):
    root = Path(root)
    nodes = r.NodeExecutorRegistry()
    nodes.register(
        r.NodeExecutorSpec("step", "Actual default capacity peer", effect="read_only", cost=1),
        CapacityNode(root, mode),
    )
    cls = AcknowledgementRuntime if mode == "delay-ack" else TemporalRuntime
    # Deliberately omit tool_execution: the product's node default must be16.
    runtime = cls(providers={}, tools=r.ToolRegistry(), workflow_executors=nodes)
    if mode == "delay-ack":
        runtime.fixture_root = root
    return runtime


async def close_runtime(runtime):
    await runtime.close_context_execution(wait_timeout=10)
    await runtime.tool_execution.aclose(wait_timeout=10)


async def worker_main(root, mode, label):
    from temporalio.client import Client

    root = Path(root)
    client = await Client.connect(
        os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
        namespace=os.environ.get("RALF_TEST_TEMPORAL_NAMESPACE", "default"),
    )
    runtime = make_runtime(root, mode)
    try:
        # An independent Activity-only Worker retains its real handlers across
        # this process restart. This process exclusively hosts original History.
        async with build_temporal_worker(
            client,
            task_queue=os.environ["RALF_NODE_CAPACITY_QUEUE"],
            runtime=runtime,
            release=runtime.orchestration_release,
            no_remote_activities=True,
        ):
            ready = root / ("ready-" + label + ".json")
            pending = root / ("ready-" + label + ".pending")
            pending.write_text(
                json.dumps(
                    {
                        "package": r.__file__,
                        "release": runtime.orchestration_release,
                        "workflow_only": True,
                    }
                )
            )
            pending.replace(ready)
            while not (root / ("stop-" + label)).exists():  # noqa: ASYNC110 -- test owns stop marker
                await asyncio.sleep(0.02)
        (root / ("closed-" + label)).touch()
    finally:
        await close_runtime(runtime)


if __name__ == "__main__":
    from tests.temporal_node_capacity_worker import worker_main as imported_main

    asyncio.run(
        imported_main(
            Path(os.environ["RALF_NODE_CAPACITY_ROOT"]),
            os.environ["RALF_NODE_CAPACITY_MODE"],
            os.environ["RALF_NODE_CAPACITY_LABEL"],
        )
    )
