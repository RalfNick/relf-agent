"""Editable application asset exported by the default starter, not a new SDK API."""

import json

from agent_app.journey import main as run_journey

from relf_agent import InMemoryMemory, ModelResponse, ToolCall, ToolRegistry
from relf_agent.errors import ValidationError


class SupportModel:
    """Replace complete with your model integration; this fixture is offline."""

    identity = {"kind": "my-support-model", "version": "1"}

    async def complete(self, messages, tools):
        observations = [message for message in messages if message["role"] == "tool"]
        if not observations:
            return ModelResponse(tool_calls=[ToolCall("lookup_ticket", {"ticket_id": "INC-001"})])
        return ModelResponse(
            {"source": "custom-model", "ticket": json.loads(observations[-1]["content"])}
        )


def custom_tools():
    tools = ToolRegistry()

    @tools.tool(effect="read_only", description="Read the application's ticket")
    async def lookup_ticket(ticket_id: str):
        if ticket_id != "INC-001":
            raise ValidationError("The fixture contains only INC-001")
        # Await your own read-only API here; the Engine still owns dispatch.
        return {
            "ticket_id": ticket_id,
            "service": "payments",
            "status": "degraded",
            "source": "custom-lookup",
        }

    return tools


def memory_for_example(*, ephemeral=False):
    # None keeps persistent SQLite. InMemoryMemory lives only in this process;
    # it cannot recover a previous process's Session or fixed memory identity.
    return InMemoryMemory() if ephemeral else None


def main(argv=None):
    return run_journey(
        argv,
        provider=SupportModel(),
        tools=custom_tools(),
        memory=memory_for_example(ephemeral=False),
    )


if __name__ == "__main__":
    raise SystemExit(main())
