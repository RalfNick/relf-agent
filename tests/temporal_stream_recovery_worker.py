"""Stream recovery fixture: a read-only handler loses its synthetic receipt."""

import json
import os

import relf_agent as r


class Business:
    def __init__(self, root, mode):
        self.root, self.mode = root, mode

    def audit(self, context, kind):
        with (self.root / "calls.jsonl").open("a") as output:
            output.write(
                json.dumps(
                    {
                        "kind": kind,
                        "pid": os.getpid(),
                        "effect_key": context.effect_key,
                        "run_id": context.run_id,
                    }
                )
                + "\n"
            )
            output.flush()
            os.fsync(output.fileno())

    async def lookup(self, arguments, context):
        await r.emit_tool_delta({"stage": "lookup"})
        self.audit(context, "dispatch")
        result = {"value": arguments["value"] + 1}
        if self.mode == "unknown":
            receipt = self.root / (context.effect_key.split(":")[-1] + ".receipt")
            receipt.write_text(json.dumps(result))
            raise ConnectionError("Fixture lost the completed business receipt")
        return result

    async def reconcile(self, arguments, context):
        self.audit(context, "query")
        receipt = self.root / (context.effect_key.split(":")[-1] + ".receipt")
        return json.loads(receipt.read_text()) if receipt.exists() else None


class PrepareProvider:
    identity = {"kind": "direct-tools-fixed-agent-fixture", "version": "1"}

    def __init__(self, root):
        self.root = root

    async def complete(self, messages, tools):
        with (self.root / "model-calls.jsonl").open("a") as output:
            output.write(json.dumps({"pid": os.getpid()}) + "\n")
        return r.ModelResponse(output={"value": 4})


class CallingProvider(PrepareProvider):
    identity = {"kind": "direct-tools-calling-agent-fixture", "version": "1"}

    async def complete(self, messages, tools):
        await super().complete(messages, tools)
        if any(message["role"] == "tool" for message in messages):
            return r.ModelResponse("done")
        return r.ModelResponse(tool_calls=[r.ToolCall("lookup", {"value": 4}, "read")])


def tools(root, *, mode="normal"):
    selected, business = r.ToolRegistry(), Business(root, mode)
    selected.register(
        r.ToolSpec(
            "lookup",
            "Read a value",
            {"type": "object"},
            requires_approval=True,
            config={"fixture_mode": mode},
        ),
        business.lookup,
        reconciler=business.reconcile,
    )
    return selected
