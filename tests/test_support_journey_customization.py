"""Application replacement hooks must use normal SDK ports and borrowed resources."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import relf_agent as r


def example():
    path = Path(__file__).parents[1] / "examples/support_journey.py"
    spec = importlib.util.spec_from_file_location("support_journey_custom_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CustomProvider:
    identity = {"kind": "support-custom-test", "version": "1"}

    def __bool__(self):
        return False

    async def complete(self, messages, tools):
        observed = [m for m in messages if m.get("role") == "tool"]
        if not observed:
            return r.ModelResponse(
                tool_calls=[r.ToolCall("lookup_ticket", {"ticket_id": "INC-001"})]
            )
        return r.ModelResponse({"custom": json.loads(observed[-1]["content"])})


def test_injected_model_and_async_tool_are_used_without_provider_counter(tmp_path, capsys):
    calls, tools = [], r.ToolRegistry()

    @tools.tool(effect="read_only")
    async def lookup_ticket(ticket_id: str):
        calls.append(ticket_id)
        return {"ticket_id": ticket_id, "status": "custom-backend"}

    status = example().main(
        ["agent", "--data-dir", str(tmp_path / "app"), "--command-id", "custom"],
        provider=CustomProvider(),
        tools=tools,
    )
    output = json.loads(capsys.readouterr().out)
    assert status == 0 and output["state"] == "succeeded"
    assert output["result"]["custom"]["status"] == "custom-backend"
    assert output["model_calls"] is None and calls == ["INC-001"]


def test_borrowed_memory_can_be_reused_across_session_turns(tmp_path, capsys):
    class Memory(r.InMemoryMemory):
        closes = 0

        def close(self):
            self.closes += 1

    memory, module = Memory(), example()
    outputs = []
    for command in ("first", "second"):
        assert (
            module.main(
                ["session", "--data-dir", str(tmp_path / "app"), "--command-id", command],
                memory=memory,
            )
            == 0
        )
        outputs.append(json.loads(capsys.readouterr().out))
    assert outputs[0]["result"]["session_records"] == 0
    assert outputs[1]["result"]["session_records"] >= 1
    assert memory.closes == 0


def test_existing_async_memory_adapter_is_awaited_for_seed_facts(tmp_path, capsys):
    backend = r.InMemoryMemory()
    memory = r.ThreadedMemoryAdapter(backend)
    result = example().main(
        ["memory", "--data-dir", str(tmp_path / "app"), "--command-id", "async"], memory=memory
    )
    output = json.loads(capsys.readouterr().out)
    assert result == 0 and output["result"]["facts"]["response-style"] == "concise"
    assert backend.inspect_fact(r.Scope(), "support", "response-style")["version"] == 1


def test_explicit_empty_tool_registry_does_not_select_default(tmp_path, capsys):
    status = example().main(
        ["agent", "--data-dir", str(tmp_path / "app"), "--command-id", "empty"],
        tools=r.ToolRegistry(),
    )
    output = json.loads(capsys.readouterr().out)
    assert status == 2 and output["error"] == "definition_mismatch"


@pytest.mark.parametrize("arguments", [["--provider", "deepseek-chat"], ["--model", "explicit"]])
def test_live_config_and_injected_model_do_not_silently_override_each_other(
    tmp_path, capsys, arguments
):
    directory = tmp_path / "unopened"
    result = example().main(
        ["agent", "--data-dir", str(directory), "--command-id", "invalid", *arguments],
        provider=CustomProvider(),
    )
    assert result == 2 and json.loads(capsys.readouterr().out)["error"] == "validation_error"
    assert not directory.exists()


def test_default_starter_exports_editable_journey_and_replacement_example(tmp_path):
    from relf_agent.starter import create_starter

    project = create_starter(tmp_path / "app")
    assert project.template == "oncall" and project.module == "agent_app"
    assert {"agent_app/journey.py", "agent_app/customize.py"} <= set(project.files)
    source = Path(__file__).parents[1] / "examples/support_journey.py"
    assert (Path(project.directory) / "agent_app/journey.py").read_bytes() == source.read_bytes()


def generated_output(directory, module, *arguments):
    environment = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
    package_parent = Path(r.__file__).resolve().parent.parent
    if package_parent.name == "src":
        environment["PYTHONPATH"] = str(package_parent)
    result = subprocess.run(
        [sys.executable, "-m", module, *arguments],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


@pytest.mark.parametrize("stage", ["agent", "session", "rag", "memory", "workflow"])
def test_generated_journey_runs_and_reuses_original_receipts(tmp_path, stage):
    from relf_agent.starter import create_starter

    directory = Path(create_starter(tmp_path / "app").directory)
    first = generated_output(directory, "agent_app.journey", stage, "--command-id", "first")
    again = generated_output(directory, "agent_app.journey", stage, "--command-id", "first")
    assert first["state"] == again["state"] == "succeeded"
    assert first["run_id"] == again["run_id"] and first["result"] == again["result"]
    assert first["model_calls"] >= 2 and again["model_calls"] == 0


def test_generated_customization_replaces_model_and_async_tool_with_durable_default(tmp_path):
    from relf_agent.starter import create_starter

    directory = Path(create_starter(tmp_path / "app").directory)
    options = ["agent", "--data-dir", ".ralf/custom", "--command-id", "custom"]
    first = generated_output(directory, "agent_app.customize", *options)
    again = generated_output(directory, "agent_app.customize", *options)
    assert first["state"] == again["state"] == "succeeded"
    assert first["result"] == again["result"]
    assert first["result"]["source"] == "custom-model"
    assert first["result"]["ticket"]["source"] == "custom-lookup"
    assert first["run_id"] == again["run_id"]


def test_generated_session_continues_in_another_process(tmp_path):
    from relf_agent.starter import create_starter

    directory = Path(create_starter(tmp_path / "app").directory)
    first = generated_output(directory, "agent_app.journey", "session", "--command-id", "turn-1")
    second = generated_output(directory, "agent_app.journey", "session", "--command-id", "turn-2")
    assert first["result"]["session_records"] == 0
    assert second["result"]["session_records"] >= 1
