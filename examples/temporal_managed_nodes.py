"""Run the default no-model nodes against an explicitly selected Temporal Service."""

import argparse
import asyncio
import json

from relf_agent import (
    GraphNode,
    GraphWorkflowSpec,
    TemporalProfile,
    TemporalRuntimeBuilder,
    ValueRef,
)
from relf_agent.errors import ValidationError


def definition():
    return GraphWorkflowSpec(
        "temporal-identity-nodes",
        [
            GraphNode("first", executor="identity"),
            GraphNode(
                "second", executor="identity", depends_on=("first",), input=ValueRef("first")
            ),
        ],
        output=ValueRef("second"),
    )


async def run(args):
    from temporalio.client import Client

    selected = TemporalProfile(
        "identity-nodes",
        "1",
        {},
        {"workflow_executors": {"adapter": "identity", "config": {}}},
    )
    client = await Client.connect(args.address)
    assembly = await TemporalRuntimeBuilder().abuild(selected)
    try:
        await assembly.start_worker(client, task_queue=args.task_queue)
        engine = assembly.create_engine(client, task_queue=args.task_queue)
        handle = await engine.submit(
            definition(),
            json.loads(args.input_json),
            command_id=args.command_id,
            budget=2,
        )
        result = await engine.drive(handle.run_id, wait_seconds=30)
        diagnostics = await engine.diagnostics(handle.run_id)
        if result.state != "succeeded":
            raise ValidationError(f"Original Run remains {result.state}: {handle.run_id}")
        return {
            "run_id": handle.run_id,
            "state": result.state,
            "result": result.result,
            "budget": diagnostics.budget,
            "submission_receipt": handle.to_dict()["receipt"],
        }
    finally:
        await assembly.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default="localhost:7233")
    parser.add_argument("--task-queue", default="relf-example-nodes")
    parser.add_argument("--command-id", required=True)
    parser.add_argument("--input-json", default='[1, null, {"message": "完整 JSON"}]')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False))


if __name__ == "__main__":
    main()
