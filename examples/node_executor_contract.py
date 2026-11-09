"""Editable independent component; run with the current SDK, without a model/service.

Replace ExampleNode with your own async component and provide fixture controls
for a disposable test environment. The suite owns verdicts and Local Run state.
This example has no durable business backend; reopening verifies the Engine's
SQLite records while keeping the same application object and identity.
"""

import argparse
import asyncio
import copy
import json

from relf_agent import (
    AdapterContractSuite,
    NodeContractPause,
    NodeContractResource,
    NodeContractSession,
)


class ExampleNode:
    def __init__(self, resource_id):
        self.resource_id, self.version = resource_id, "1"
        self.output = None
        self.calls, self.closes, self.active = [], 0, 0
        self.closed, self.fail, self.gate = False, False, None

    @property
    def identity(self):
        return {"kind": "my-example-node", "version": self.version, "resource": self.resource_id}

    async def execute(self, input, config, context):
        if self.closed:
            raise RuntimeError("Example client closed")
        self.calls.append(copy.deepcopy((input, config, context.effect_key)))
        self.active += 1
        try:
            if self.fail:
                raise RuntimeError("Private example supplier failure")
            if self.gate is not None:
                entered, released = self.gate
                entered.set()
                while not released.is_set():
                    try:
                        await released.wait()
                    except asyncio.CancelledError:
                        continue
            return copy.deepcopy(self.output)
        finally:
            self.active -= 1

    def configure(self, kind, data):
        if kind != "output" or set(data) != {"result"}:
            raise ValueError("Only configured output is supported")
        self.output = copy.deepcopy(data["result"])

    def inject_fault(self, kind):
        if kind == "identity-drift":
            self.version = "changed"
        elif kind == "method-drift":

            async def replacement(input, config, context):
                raise AssertionError("Replacement must not execute")

            self.execute = replacement
        elif kind == "handler-error":
            self.fail = True
        elif kind == "reset":
            self.version, self.fail = "1", False
            self.__dict__.pop("execute", None)
        else:
            raise ValueError("Unknown fixture fault")

    def pause(self, operation):
        if operation != "execute":
            raise ValueError("Unknown fixture pause")
        entered, released = self.gate = asyncio.Event(), asyncio.Event()

        async def wait_entered():
            await entered.wait()

        async def release():
            released.set()

        return NodeContractPause(wait_entered, release)

    def audit(self):
        return {"execute_calls": len(self.calls), "reconcile_calls": 0, "close_calls": self.closes}

    def close(self):
        if self.active:
            raise RuntimeError("Original work still active")
        if not self.closed:
            self.closed = True
            self.closes += 1

    def reopen(self):
        self.close()
        self.closed = False


class ExampleFixture:
    def prepare(self, case_id, workspace):
        node = ExampleNode(str(workspace.resolve()))
        return NodeContractSession(
            node,
            resources=(NodeContractResource(node),),
            configure=node.configure,
            inject_fault=node.inject_fault,
            pause=node.pause,
            audit=node.audit,
            reopen=node.reopen,
        )


async def run(evidence_dir=None):
    suite = AdapterContractSuite(role="node-executor")
    try:
        return await suite.run(ExampleFixture(), evidence_dir=evidence_dir)
    finally:
        await suite.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", help="New private evidence directory")
    arguments = parser.parse_args()
    report = asyncio.run(run(arguments.evidence_dir)).to_dict()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
