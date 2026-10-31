"""Execute bilingual tutorial examples against the pinned SDK source, offline only.

Requires the SDK's base dependencies in the current Python environment. All
databases and the extracted SDK live in a temporary directory. The paid model
example is checked with a substituted deterministic Provider, never an endpoint.
"""

import ast
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

WEBSITE = Path(__file__).resolve().parents[1]
ROOT = WEBSITE.parent
BASELINE = json.loads((WEBSITE / "repository.json").read_text())["ref"]

FIXTURE = """from relf_agent import ModelResponse, ToolCall
class _OfflineFixture:
    identity = {"kind": "website-model-smoke", "version": "1"}
    async def complete(self, messages, tools):
        if not any(m["role"] == "tool" for m in messages):
            return ModelResponse(tool_calls=(ToolCall("lookup", {"ticket": "INC-001"}, "one"),))
        return ModelResponse(output={"ticket": "INC-001", "status": "open"})
"""


def blocks(locale, slug, language="python"):
    source = (WEBSITE / f"src/content/guides/{locale}/{slug}.md").read_text()
    return re.findall(rf"```{language}\n(.*?)\n```", source, re.S)


def run(args, cwd, env):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise AssertionError(f"{args}:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def execute(code, path, env):
    path.write_text(code)
    return run([sys.executable, str(path)], path.parent, env)


def json_records(output):
    """Read command JSON alongside text from init or inspect commands."""
    result = []
    decoder = json.JSONDecoder()
    offset = 0
    while offset < len(output):
        start = output.find("{", offset)
        if start < 0:
            break
        try:
            value, size = decoder.raw_decode(output[start:])
        except ValueError:
            offset = start + 1
            continue
        if isinstance(value, dict) and "run_id" in value and "state" in value:
            result.append(value)
        offset = start + size
    return result


def substitute(code, values):
    for key, value in values.items():
        assert re.fullmatch(r"[A-Za-z0-9_:-]+", value), (key, value)
        code = code.replace(key, value)
    return code


def verify_command_recipes(locale, directory, sdk, env):
    def bash(code, cwd):
        assert "--provider" not in code, "Live-provider examples are outside offline verification"
        return run(["bash", "-eu", "-c", code], cwd, env)

    quickstart = blocks(locale, "quickstart", "bash")
    checkout = directory / "quickstart" / "sdk"
    checkout.mkdir(parents=True)
    initial = json_records(bash(quickstart[1], checkout))[-1]
    assert initial["state"] == "waiting_approval", initial
    proposal = initial["pending"][0]
    refs = {
        "RUN_ID": initial["run_id"],
        "ACTION_ID": proposal["action_id"],
        "OPERATION_DIGEST": proposal["digest"],
    }
    application = checkout.parent / "my-agent"
    assert "waiting_approval" in bash(substitute(quickstart[2], refs), application)
    assert "succeeded" in bash(substitute(quickstart[3], refs), application)
    repeated = json_records(bash(quickstart[4], application))[-1]
    assert repeated["state"] == "succeeded" and repeated["run_id"] == initial["run_id"]

    user_input = blocks(locale, "user-input", "bash")
    input_root = directory / "cli-input"
    input_root.mkdir()
    question = json_records(bash(user_input[0], input_root))[-1]
    assert question["state"] == "waiting_input", question
    pending = question["pending"][0]
    refs = {
        "RUN_ID": question["run_id"],
        "PENDING_ID": pending["pending_id"],
        "TARGET_DIGEST": pending["target_digest"],
    }
    input_app = input_root / "input-app"
    assert "waiting_input" in bash(substitute(user_input[1], refs), input_app)
    bash(substitute(user_input[2], refs), input_app)
    assert "succeeded" in bash(substitute(user_input[3], refs), input_app)

    journey = blocks(locale, "app-tutorial", "bash")
    checkout = directory / "application" / "sdk"
    checkout.mkdir(parents=True)
    bash(journey[0], checkout)
    app = checkout.parent / "support-app"
    agent = json_records(bash(journey[1], app))
    assert len(agent) == 2 and all(r["state"] == "succeeded" for r in agent)
    assert agent[0]["run_id"] == agent[1]["run_id"]
    session = json_records(bash(journey[3], app))
    assert len(session) == 3 and all(r["state"] == "succeeded" for r in session)
    assert session[0]["run_id"] != session[1]["run_id"] == session[2]["run_id"]
    rag = json_records(bash(journey[4], app))[-1]
    assert rag["state"] == "succeeded" and "cache-recovery" in json.dumps(rag)
    memory = json_records(bash(journey[5], app))
    assert len(memory) == 2 and all(r["state"] == "succeeded" for r in memory)
    assert all(r["result"]["facts"] == {"response-style": "concise"} for r in memory)
    workflow = json_records(bash(journey[6], app))[-1]
    assert workflow["state"] == "succeeded" and workflow["model_calls"] == 4
    observed = bash(substitute(journey[7], {"RUN_ID": session[1]["run_id"]}), app)
    assert session[1]["run_id"] in observed and "succeeded" in observed
    custom = json_records(bash(journey[8], app))
    assert len(custom) == 2 and all(row["state"] == "succeeded" for row in custom)
    assert custom[0]["run_id"] == custom[1]["run_id"]
    assert custom[0]["result"] == custom[1]["result"]
    assert custom[0]["result"]["source"] == "custom-model"
    assert custom[0]["result"]["ticket"]["source"] == "custom-lookup"
    assert all(row["model_calls"] is None for row in custom)
    # journey[2] is the explicit live-model example and is never executed here.
    evaluations = blocks(locale, "testing", "bash")
    offline = next(code for code in evaluations if "relf-evaluate-business --offline" in code)
    evaluation_dir = directory / "offline-evaluations"
    evaluation_dir.mkdir()
    bash(offline, evaluation_dir)
    expected = {"business": (8, 15), "rag": (8, 8), "plan": (5, 17), "team": (5, 17)}
    for name, (total, calls) in expected.items():
        report = json.loads((evaluation_dir / f"{name}.json").read_text())
        assert report["status"] == "completed", (name, report)
        assert report["passed"] == report["total"] == total, (name, report)
        assert report["calls"] == calls and report["model_quality"] is None, (name, report)
    print(
        f"{locale}: CLI approval/restart, durable input, five-stage application and four offline evaluations passed"
    )


def verify_maintenance_recipes(locale, directory, sdk, env):
    facade = next(code for code in blocks(locale, "models-tools") if "class OfflineTicket:" in code)
    facade_runs = [
        json_records(execute(facade, directory / "facade_agent.py", env))[-1] for _ in range(2)
    ]
    assert all(row["state"] == "succeeded" for row in facade_runs)
    assert facade_runs[0]["run_id"] == facade_runs[1]["run_id"]
    assert facade_runs[0]["result"] == {"ticket": "INC-001", "status": "open"}

    observation = next(
        code for code in blocks(locale, "operations") if "class OfflineObservation:" in code
    )
    observed = [
        json_records(execute(observation, directory / "observe_agent.py", env)) for _ in range(2)
    ]
    assert all(len(rows) == 2 for rows in observed)
    assert len({row["run_id"] for rows in observed for row in rows}) == 1
    assert all(row["state"] == "succeeded" for rows in observed for row in rows)
    assert all(rows[0]["cursor_resumed"] and rows[0]["events"] > 1 for rows in observed)
    assert all(rows[1]["reconnected"] for rows in observed)

    stream = next(
        code
        for code in blocks(locale, "operations", "bash")
        if ":examples/stream_updates.py" in code
    )
    checkout = directory / "stream" / "sdk"
    checkout.mkdir(parents=True)
    git_dir = subprocess.check_output(
        ["git", "rev-parse", "--absolute-git-dir"], cwd=ROOT, text=True
    ).strip()
    output = run(
        ["bash", "-eu", "-c", stream],
        checkout,
        {**env, "GIT_DIR": git_dir, "GIT_WORK_TREE": str(sdk)},
    )
    records = [json.loads(line) for line in output.splitlines()]
    completed = [row for row in records if "state" in row]
    assert len(completed) == 2 and all(row["state"] == "succeeded" for row in completed)
    assert completed[0]["run_id"] == completed[1]["run_id"]
    assert (completed[0]["model_calls"], completed[0]["tool_calls"]) == (2, 1)
    assert (completed[1]["model_calls"], completed[1]["tool_calls"]) == (0, 0)
    events = [row for row in records if "kind" in row]
    assert {"model_delta", "model_end", "tool_delta", "tool_end"} <= {row["kind"] for row in events}
    assert all(
        row["authoritative"] is (row["kind"] not in ("model_delta", "tool_delta", "gap"))
        for row in events
    )
    count = len(events) // 2
    assert count > 0 and events[:count] == events[count:], "Replay changed original stream evidence"

    def bash(code, cwd):
        assert "--provider" not in code, "Live-provider examples are outside offline verification"
        return run(["bash", "-eu", "-c", code], cwd, env)

    recipes = blocks(locale, "workflows", "bash")
    start = next(code for code in recipes if "init ../my-tool-flow" in code)
    checkout = directory / "tool-flow" / "sdk"
    checkout.mkdir(parents=True)
    initial = json_records(bash(start, checkout))
    assert len(initial) == 2 and initial[0]["run_id"] == initial[1]["run_id"]

    def assert_tool_result(row):
        assert row["state"] == "succeeded", row
        assert (row["model_actions"], row["tool_actions"], row["credits_spent"]) == (0, 2, 2), row
        assert row["result"]["available"] is True, row

    for row in initial:
        assert_tool_result(row)
    app = checkout.parent / "my-tool-flow"
    queued_code = next(code for code in recipes if "--order-id ORD-2" in code)
    queued = json_records(bash(queued_code, app))[-1]
    assert queued["state"] == "queued" and queued["tool_actions"] == 0, queued
    resume = next(
        code
        for code in recipes
        if "agent_app.tool_runtime:create_engine resume" in code and "DECISION_ID" not in code
    )
    resumed = json_records(bash(substitute(resume, {"RUN_ID": queued["run_id"]}), app))[-1]
    assert resumed["state"] == "succeeded", resumed

    approval_start = next(code for code in recipes if "init ../approved-tool-flow" in code)
    pending = json_records(bash(approval_start, app))[-1]
    assert pending["state"] == "waiting_approval", pending
    assert (pending["model_actions"], pending["tool_actions"], pending["credits_spent"]) == (
        0,
        1,
        0,
    ), pending
    approved_app = app.parent / "approved-tool-flow"
    control = next(code for code in recipes if "DECISION_ID" in code)
    for number in range(2):
        action = pending["pending"][0]
        refs = {
            "RUN_ID": pending["run_id"],
            "ACTION_ID": action["action_id"],
            "OPERATION_DIGEST": action["digest"],
            "DECISION_ID": f"approve-tool-{number + 1}",
        }
        commands = substitute(control, refs)
        pending = json_records(bash(commands, approved_app))[-1]
        repeated_approval = next(line for line in commands.splitlines() if " approve " in line)
        bash(repeated_approval, approved_app)
        assert pending["state"] == ("waiting_approval" if number == 0 else "succeeded"), pending
    repeat = "python -m agent_app.tool_graph --order-id ORD-3 --command-id order-3"
    final = json_records(bash(repeat, approved_app))[-1]
    assert final["run_id"] == pending["run_id"]
    assert_tool_result(final)
    print(
        f"{locale}: Agent replay, cursor/reconnect, stream replay and model-free Tool approvals passed"
    )


with TemporaryDirectory(prefix="relf-website-examples-") as tmp:
    work = Path(tmp)
    sdk = work / "sdk"
    sdk.mkdir()
    archive = subprocess.check_output(
        ["git", "archive", BASELINE, "src", "examples", "pyproject.toml"], cwd=ROOT
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(sdk, filter="data")
    env = {
        **{key: os.environ[key] for key in ("LANG", "LC_ALL", "TEMP", "TMP") if key in os.environ},
        "PYTHONPATH": str(sdk / "src"),
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
    }

    for locale in ("zh", "en"):
        directory = work / locale
        directory.mkdir()
        models = blocks(locale, "models-tools")
        original = next(code for code in models if "engine.submit(spec," in code)
        hook = 'OpenAIChatProvider(model=os.environ["RELF_MODEL"])'
        assert hook in original, "Update the offline substitution when the tutorial changes"
        original = FIXTURE + original.replace(hook, "_OfflineFixture()")
        schema = next(code for code in models if "output_schema=" in code)
        tree = ast.parse(original)
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "spec" for t in node.targets)
        )
        lines = original.splitlines()
        structured = "\n".join(
            lines[: assignment.lineno - 1] + [schema] + lines[assignment.end_lineno :]
        )
        guide = (WEBSITE / f"src/content/guides/{locale}/models-tools.md").read_text()
        new_id = re.search(r'command_id="(request-structured-[^\"]+)"', guide)
        assert new_id, "Structured-output instructions need a new command identity"
        structured = structured.replace('command_id="request-001"', f'command_id="{new_id[1]}"')
        path = directory / "ticket_agent.py"
        first = execute(original, path, env)
        repeated = execute(original, path, env)
        updated = execute(structured, path, env)
        for output in (first, repeated, updated):
            assert "state='succeeded'" in output, output

        def identity(output):
            return re.search(r"run_id='([^']+)'", output)[1]

        assert identity(first) == identity(repeated) != identity(updated)

        session = next(
            code for code in blocks(locale, "sessions-memory") if "class OfflineSupport" in code
        )
        for _ in range(2):
            output = execute(session, directory / "session_agent.py", env)
            assert output.count("succeeded {'order': '123'}") == 2, output

        app_test = next(
            code for code in blocks(locale, "testing") if "class OfflineProvider" in code
        )
        assert "PASS:" in execute(app_test, directory / "test_app.py", env)
        input_test = next(
            code for code in blocks(locale, "user-input") if "asyncio.run(main())" in code
        )
        assert "succeeded" in execute(input_test, directory / "input_agent.py", env)

        hybrid = next(
            code
            for code in blocks(locale, "sessions-memory", "bash")
            if "--template hybrid" in code
        )
        output = run(["bash", "-eu", "-c", hybrid], directory, env)
        assert '"status": "index_call_completed"' in output and '"grounded": true' in output, output
        print(
            f"{locale}: model→schema identity/replay, Session continuation/replay, app test, input and hybrid recipes passed"
        )
        verify_command_recipes(locale, directory, sdk, env)
        verify_maintenance_recipes(locale, directory, sdk, env)

print(
    f"Tutorial examples passed against pinned SDK source {BASELINE[:12]}; online model/embedding probes excluded."
)
