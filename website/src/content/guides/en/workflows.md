---
title: Workflows & teams
description: Choose static graphs, bounded plans or teams to match the structure of your task.
locale: en
slug: workflows
sources: [docs/static-workflows.md, docs/orchestration.md, docs/parallel-workflows.md, docs/dynamic-dag.md, docs/concepts.md, docs/user-input.md, docs/managed-tools.md, docs/runtime-assembly.md]
---

## Choose the task structure

| Structure | Suitable work |
| --- | --- |
| One `AgentSpec` | A single model-and-tool loop |
| `WorkflowSpec` / static graph | Known steps, dependencies, branches and input mapping |
| `TeamSpec` | Sequential, routed or supervised collaboration among registered members |
| `DynamicWorkflowSpec` | Planning, execution, verification and replanning within explicit limits |

Start with the smallest useful structure. Child runs retain the existing tool, approval, budget and effect-recovery protocols.

## Run a static graph

After installing the SDK, choose a directory that does not yet exist:

```bash
relf init my-graph --template graph
cd my-graph
python -m agent_app --input urgent --command-id urgent-task
```

Edit dependencies, branches and result mapping in `graph.json`. Configure providers and versions in `runtime.toml`. The template uses an offline echo provider. It demonstrates execution and assembly, not model task quality.

To submit first and continue later:

```bash
python -m agent_app --input urgent --command-id queued-task --submit-only
relf --config runtime.toml resume RUN_ID
relf --config runtime.toml --format text inspect RUN_ID
```

Static graphs support explicit dependencies, conditions, input mapping and joins. Bounded parallel execution requires an explicit `max_concurrency`. Pure transforms compute JSON data; external I/O belongs in managed tools. See the [static graph guide (Chinese)](repo:docs/static-workflows.md).

## Run async Tool flows without a model

The fixed maintenance source's graph template also generates a separate order/stock Tool application. Start from a writable working directory and choose a new target:

```bash
relf --format text init ../my-tool-flow --template graph
cd ../my-tool-flow
python -m agent_app.tool_graph --order-id ORD-1 --command-id order-1
python -m agent_app.tool_graph --order-id ORD-1 --command-id order-1
```

Both commands should return the same `run_id` and result, with `model_actions=0`, `tool_actions=2` and `credits_spent=2`. `lookup → stock` invokes two read-only async Python tools; results contain the order, SKU and availability. New orders use new command IDs. These fixtures make no real network calls or business writes.

Submit another order without driving it:

```bash
python -m agent_app.tool_graph --order-id ORD-2 --command-id order-2 --submit-only
```

Replace `RUN_ID` with that submission's actual ID, inspect, resume and confirm `succeeded`:

```bash
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine --format text inspect RUN_ID
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine resume RUN_ID
relf --db .ralf/tool-graph.sqlite --format text inspect RUN_ID
```

`tool-runtime.toml` explicitly declares `providers = {}`, `tool-graph.json` defines nodes/mappings, and `agent_app/tool_runtime.py` registers `order-fixture` and the original recovery factory. Replace its two async functions for your business. The synchronous registration factory only assembles tools; manage async clients through [async assembly (Chinese)](repo:docs/async-assembly.md), never by returning an unawaited coroutine.

Empty providers support finite **Local Tool/Transform graphs** only; the field remains required. Ordinary Agent/mixed graphs need a resolvable Provider, and TemporalProfile still requires nonempty providers. Tool nodes retain original Actions, budgets, authorization, approvals, receipts and unknown-effect reconciliation. They are not arbitrary nodes/reducers or record-by-record dataflow. Original a8 archives do not generate these files.

### Add approval to a new Tool flow

Run from `my-tool-flow` above. Change configuration only before the new project's first submission; retain old Profiles for existing Runs:

```bash
relf --format text init ../approved-tool-flow --template graph
cd ../approved-tool-flow
python -c 'from pathlib import Path; p=Path("tool-runtime.toml"); p.write_text(p.read_text().replace("requires_approval = false", "requires_approval = true"))'
python -m agent_app.tool_graph --order-id ORD-3 --command-id order-3
```

The first call pauses at `waiting_approval`: the first Tool Action exists (`tool_actions=1`), but dispatch has not happened and `credits_spent=0`. Action counts differ from actual handler call counts. Inspect the returned Run ID, take `ACTION_ID`/`OPERATION_DIGEST` from pending, and choose a distinct stable `DECISION_ID` for each decision:

```bash
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine --format text inspect RUN_ID
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine approve RUN_ID ACTION_ID --digest OPERATION_DIGEST --command-id DECISION_ID
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine resume RUN_ID
relf --db .ralf/tool-graph.sqlite --format text inspect RUN_ID
```

After approving the first node, resume may pause for the second. Inspect its new Action/digest, use a new decision ID and repeat the controls until the Snapshot is `succeeded`. Retrying the same approval uses its original ID and receipt without extra dispatch. Final counts remain two Tool Actions, zero Model Actions and two credits. This example approves read-only fixtures; writes need their real effect class and downstream idempotency/query/reconciliation contract.

## Define a team

This offline example demonstrates delegation without model credentials:

```python
import asyncio
from relf_agent import AgentSpec, RuntimeBuilder, RuntimeProfile, TeamSpec

profile = RuntimeProfile(
    "team", "1", {"default": {"adapter": "offline-echo"}},
)
team = TeamSpec(
    "review-team",
    {
        "research": AgentSpec("research", "Research"),
        "review": AgentSpec("review", "Review"),
    },
    child_budget=4,
)
with RuntimeBuilder().build(profile, ".ralf/team.sqlite") as runtime:
    handle = runtime.submit(team, "task", command_id="first", budget=8)
    print(asyncio.run(runtime.drive(handle.run_id)))
```

Default team strategies include `sequential`, `router` and `supervisor`. Members can select their own providers, tools and output constraints. The parent retains delegation identity and child-run links.

## Bound dynamic planning

A Plan uses registered planners and verifiers to propose finite steps. Configure allowed members, `max_revisions`, `max_steps`, `max_concurrency` and child budgets. Planning produces proposals; the engine still commits execution facts.

Backend support for nested combinations differs. Check the [orchestration guide (Chinese)](repo:docs/orchestration.md) for supported combinations and configuration.

## Put business steps in the right nodes

A ticket flow can read information and retrieve a runbook before diagnosis, enter a write tool only when change conditions hold, then inspect receipts and summarize. Static graphs express known dependencies and conditions without replanning the process each time.

| Responsibility | Node choice | Execution detail |
| --- | --- | --- |
| Interpret input, use tools and reach a conclusion | Agent | Model, allowed tools, output and budget are pinned |
| Call an explicit business capability | Tool | Retains actions, approval and receipts without adding model calls |
| Project fields or merge JSON | Transform | Pure synchronous computation without hidden network or database I/O |

These are Local graph choices; Temporal does not support every identical node or combination. Pass outputs through explicit mappings rather than relying on results merely mentioned in model chat.

## Understand team strategies and plan revisions

| Strategy | Collaboration | Typical use |
| --- | --- | --- |
| `sequential` | Pass the task and saved results through members in order | Research then review; diagnose then draft |
| `router` | A configured routing field selects a registered member | Route each business category to a specialist |
| `supervisor` | Bounded parallel workers followed by a named supervisor | Combine independent analysis |

Routes, roles, concurrency and budgets are explicit. Member names grant no additional tool permissions. A member's agreement does not automatically approve another member's write.

Use corresponding definitions and supported subsets for DAGs or nested members. Revisions create new logical calls without rewriting completed results, effects or approvals. An explicit verifier can propose further work within iteration and budget limits.

## Parallelism, budgets and human pauses

`max_concurrency` bounds concurrent delegation. A parent budget constrains the task; child allowances are reserved at delegation. Children awaiting recovery, uncertain effects or actual call termination can still hold capacity and credits. Changing IDs cannot bypass these obligations.

Parent and child runs are separately observable. When a child needs approval, inspect that actual child's pending action and digest, resolve its original approval or reconciliation, then advance the parent. Cancelling a parent does not establish that business writes were rolled back.

Parallelize independent branches. Express required ordering through graph dependencies. See [bounded parallel workflows (Chinese)](repo:docs/parallel-workflows.md).

## Recovery and deployment

Recovery uses the original plan, delegation identities and recorded results. Approve or reconcile the actual child run, then drive the original parent. Cancellation stops further dispatch; it does not roll back business effects.

Local execution uses its original execution store. Temporal needs explicit workers, releases and execution configuration, and takes authority from its original workflow history. A successful local run does not verify a distributed combination. Read the [Temporal execution guide](repo:docs/temporal-execution.md) and current support matrix before deployment.

For a child awaiting user input, inspect `root.pending()` and reply to the question's actual owner RunRef; see [durable input](/en/docs/user-input/). A default wait can report `control_available` while the root is still `running`, so use pending evidence to select the control. For a complete sequential application, use the [application tutorial](/en/docs/app-tutorial/); validate changes with [testing and evaluation](/en/docs/testing/).
