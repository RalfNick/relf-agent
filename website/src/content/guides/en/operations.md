---
title: Runtime & deployment
description: Choose Local or Temporal and manage versioned configuration, execution allowances, observation and resource lifetimes.
locale: en
slug: operations
sources: [docs/runtime-assembly.md, docs/agent-api.md, docs/agent-limits.md, docs/temporal-execution.md, docs/recovery-guide.md, docs/agent-stream-updates.md]
---

## Choose an execution backend

| Dimension | Local | Temporal |
| --- | --- | --- |
| Execution authority | Original local execution store and coordinator | Original workflow history |
| Starting dependencies | Python, local SQLite and the application factory | Explicit Temporal service, workers, task queue and release configuration |
| Progress | `drive` or a hosted runtime advances the original run | Service/workers execute; the facade sends controls and observes progress |
| Recovery | Original database, factory, component versions and business evidence | Original history, matching release, queue and effect evidence |
| Starting use | Local assistants, development pilots and low-dependency flows | Selected distributed combinations needing independent workers |

Local does not automatically become a distributed scheduler. Temporal does not wrap LocalEngine in an activity. They share concepts without complete parity for sessions, tool nodes or nested combinations. Temporal is explicitly configured within its experimental Alpha scope. Read the [Temporal guide](repo:docs/temporal-execution.md) and [current support status (Chinese)](repo:docs/implementation-status.md) before choosing it.

This website is static and can be hosted on Cloudflare. A Python agent application needs its own Python execution environment or worker. Hosting the website does not run an agent or provide a Temporal service.

## Manage components with a profile

After source installation, generate a new offline configuration project:

```bash
relf init my-config-agent --template config
cd my-config-agent
python -m agent_app --input hello --command-id hello-1
python -m agent_app --input pending --command-id pending-1 --submit-only
relf --config runtime.toml --format text inspect RUN_ID
relf --config runtime.toml resume RUN_ID
```

Replace `RUN_ID` with the second submission's ID. `runtime.toml` defines runtime components; `agent.toml` defines the agent. The template's `offline-echo` provider verifies assembly and execution.

A basic profile has the following shape. The template already contains editable, complete configuration:

```toml
schema_version = 1
[default]
name = "assistant"
version = "1"

[[profiles]]
name = "assistant"
version = "1"
[profiles.providers.default]
adapter = "offline-echo"
[profiles.providers.default.config]
label = "example"
```

Configuration selects registered components without executing Python or dynamically importing arbitrary plugins. Relative resource paths resolve from the configuration directory. Across directories, retain the same absolute database and configuration paths and keep the original factory importable. Asynchronously constructed resources use the corresponding async assembly entry point.

## Change configuration and recover old tasks

A profile's `name/version` identifies configuration that cannot be overwritten. Moving a default affects new tasks; old runs resolve their original profiles. Retain declarations, adapter implementations and data. The catalog does not archive code or migrate databases for you.

The same command ID and request retrieve the original task. Changed input with the same ID conflicts. Use a new command ID for a new task under new configuration. Resolve `definition_mismatch` by restoring the original version, rather than changing aliases or relaxing defaults.

## Allowances, limits and completion checks

| Mechanism | What it controls | What it does not establish |
| --- | --- | --- |
| Run `budget` | Integer execution credits reserved and settled for attempts | Currency, exact tokens or a hard provider spending cap |
| Agent limits | Decisions, context characters and distinct tool-action counts | Host-wide CPU, concurrency, rate or actual remote termination |
| Graph/plan limits | Steps, revisions, concurrency and child budgets | Arbitrary scale or correct planning |
| Output schema / verifier | Output structure and explicit completion conditions | Truthful model text or automatic business success from a tool response |

Effective agent limits combine the spec, host and selected policy constraints. Pure limit policies perform no I/O and cannot expand permissions. Recovering an existing action does not allocate a new distinct tool-action slot. Limits are pinned with the original task.

## Observe, control and shut down

`status`, `events`, `inspect` and `attach` observe execution. A wait can end at a pause or observation timeout; inspect the snapshot's actual state. Resume explicitly when needed and submit a separate cancellation command to cancel.

At shutdown, stop new admission, finish or cancel and await your execution tasks, then close owned clients and data connections. Directly injected borrowed components remain their owner's responsibility. A cancelled Python await does not prove that a tool thread, subprocess or uncertain remote write has finished.

Backups need execution records, selected session/fact/knowledge/artifact stores and business-effect evidence. Copying one idle database file does not establish complete application recovery. See the [recovery guide (Chinese)](repo:docs/recovery-guide.md) for concrete procedures.

## Observe events and reconnect with Agent

In a separate directory with the fixed maintenance source installed, save `observe_agent.py` and run `python observe_agent.py`. This complete offline example submits and waits, reads one durable event, continues from its delivered cursor, then closes and reopens the same database to reconnect.

```python
import asyncio
import json
from contextlib import aclosing
from relf_agent import Agent, EventCursor, ModelResponse, RunRef

class OfflineObservation:
    identity = {"kind": "website-observation", "version": "1"}

    async def complete(self, messages, tools):
        return ModelResponse(output={"ok": True})

async def main():
    async with Agent(model=OfflineObservation(), name="observer",
                     db_path=".ralf/observe.sqlite") as agent:
        run = await agent.submit("Check locally", command_id="observe-1")
        observed = await run.wait(wait_timeout=10)
        assert observed.snapshot.state == "succeeded"
        saved_ref = run.ref.to_dict()
        async with aclosing(run.subscribe_events(
            follow=False, max_events=1
        )) as events:
            first = [record async for record in events]
        last = first[-1].cursor.token
        async with aclosing(run.subscribe_events(
            after=EventCursor.from_token(last), follow=False, page_size=2
        )) as events:
            remaining = [record async for record in events]
        assert remaining and remaining[0].event.seq > first[-1].event.seq
        print(json.dumps({"run_id": run.ref.run_id, "state": observed.snapshot.state,
                          "cursor_resumed": True, "events": len(first + remaining)}))

    async with Agent(model=OfflineObservation(), name="observer",
                     db_path=".ralf/observe.sqlite") as reopened:
        attached = reopened.runtime.attach(RunRef.from_dict(saved_ref))
        snapshot = await attached.status()
        print(json.dumps({"run_id": attached.ref.run_id, "state": snapshot.state,
                          "reconnected": True}))

asyncio.run(main())
```

Both outputs should be `succeeded` with the same `run_id`; the first includes `cursor_resumed=true`, the second `reconnected=true`. Repeating the script retrieves the original request. Saving a `RunRef` does not back up the database or provide authentication. This example reattaches a completed Run; queued or paused work needs explicit resume/approval/input with the original configuration. Attach itself does not execute it.

`subscribe_events()` returns a subscription directly; use `aclosing`. `follow=True` continues through human pauses; use `follow=False` for finite history. Retain only successfully delivered `.cursor.token` values, not bare sequence numbers in place of Scope/Run-bound reconnect tokens. `read_timeout` limits one read; wrap consumption in `asyncio.timeout` for an overall deadline. Closing, cancelling or timing out observation does not cancel business work or close the borrowed Runtime.

## Explicit model text and async-tool progress

Return to the **fixed framework checkout root** used for installation, keep its environment active and choose a new `../stream-app` directory:

```bash
mkdir ../stream-app
git show 300c62ce8dd417df6b471ce1c10a1b7a562d2c46:examples/stream_updates.py > ../stream-app/stream_updates.py
cd ../stream-app
python stream_updates.py --db .ralf/stream-example.sqlite --command-id stream-1
python stream_updates.py --db .ralf/stream-example.sqlite --command-id stream-1
```

The first final JSON should be `succeeded`, `model_calls=2`, `tool_calls=1`. The second retrieves the same Run and original events with both actual call counts at 0. The example is entirely offline; select adapters and credentials separately for real models. Copying this pinned application does not require importing the repository's `examples` package.

It explicitly selects `StreamUpdatePolicy()` for a new Run, wraps the model as `StreamedModelProvider(base, chunk_chars=8)`, and calls `emit_tool_delta(...)` from its async tool. A standalone Agent accepts `stream_updates` in its constructor; a shared Agent retains the Runtime policy. Display is off by default; changed policy needs new configuration and request identity.

| Event | Interpretation |
| --- | --- |
| `model_delta` / `tool_delta` | Nonauthoritative text/JSON progress for display |
| `gap` | Nonauthoritative truncation or transport-gap notice; display may be incomplete |
| `model_end` / `tool_end` | Original response, receipt or unknown-result fact recorded; not proof of Run success or all remote handlers stopping |
| `run` | Other original durable Run facts; inspect `handle.status()`, Actions and effect evidence for outcomes |

Defaults per Attempt are 64 deltas, 64 KiB total and 4 KiB per delta. A limit records one gap and stops further display while the full response still proceeds through original validation/adoption. This is not unlimited event retention, model reasoning, arbitrary stdout capture or Workflow node dataflow. Cancelling a subscription stops only observation; explicitly call the original handle's `cancel(command_id=...)` to cancel business work.

The complete response returns only after EOF and validation; partial text cannot dispatch tools. The wrapper borrows its underlying Provider. Drain active work using the original Runtime rules; for failed custom-iterator closes, inspect `pending_stream_closes` and explicitly `await model.retry_stream_closes()`, retaining the cleanup obligation. A subscription has one consumer; create separate subscriptions and cursors for multiple observers.

Temporal signals are accepted by the original History/Worker. Service evidence covers only selected native-text Agent cases; these offline examples add no qualification for advanced Temporal streams, real writes, hosted models or platforms. See the [streaming contract (Chinese)](repo:docs/agent-stream-updates.md).

## Continue from a local pilot

Validate an offline task, a real tool and approval/recovery first. Add dependencies and services for your chosen models, remote data, MCP or Temporal. From the source repository root, install the Temporal extra with `python -m pip install -e '.[temporal]'`, then provide the service, workers and matching release. This guide starts no services implicitly.

APIs and some combinations remain Alpha. Evaluate deployment using evidence from your actual components and failure scenarios; current qualification is in the [implementation status (Chinese)](repo:docs/implementation-status.md). Use [approval and recovery](/en/docs/recovery/) to diagnose execution by state.

## Verified baseline and support boundaries

This site documents the SDK **0.1.0a8 maintenance source** at the pinned commit shown above, verified on **2026-10-31**. The date records these tutorial checks, not a guarantee for every deployment or hosted model.

| Combination | Documentation status | Your next verification |
| --- | --- | --- |
| Local + SQLite + offline models/tools | Tutorial baseline | Run quickstart and the application test |
| Local Sessions, durable input, lexical/hybrid retrieval and explicit Facts | Offline recipes provided | Run the application and input tutorials with your own cases |
| Real models, embeddings and external tools | Explicit adapters and configuration | Check the exact endpoint, permissions, errors, cleanup and business outcomes |
| Remote storage or Temporal workers/releases | Experimental supported subsets | Follow the selected backend guide; these website tutorials do not verify those service combinations |

Use [API & CLI reference](/en/docs/api-reference/) for signatures, [durable user input](/en/docs/user-input/) for pauses, and [testing and evaluation](/en/docs/testing/) before changing providers or deploying. The pinned technical sources describe that snapshot; newer repository development does not change old-run recovery requirements.
