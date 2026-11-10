# Dynamic DAG and nested orchestration

## 当前能力入口：2026-11-10

开发源码基线为已登记推送的 `aa77b90`。现有动态 DAG、嵌套成员和原父子 Run 协议继续使用；Local 通用受管理异步节点，以及 Temporal 所选无会话串并行／混合图和 Team／Dynamic 嵌套 executor 已有实现与分层证据，见[Local 节点](managed-async-nodes.md)、[Temporal 节点](temporal-managed-nodes.md)及[当前交付](current-delivery.md)。不能把下方 dev15 的 Temporal 拒绝范围当作当前源码总能力。

本批增加显式 `FanOutDAGPlanner`，将有限列表编译为原 DAG 的独立 Worker 和可选汇总成员；不新增调度权威或绑定格式。结果按输入索引的稳定 `map-0000` 等键收集，汇总节点计入原步骤／预算限制。完整无模型应用、SDK 与 JSON／TOML 入口见[有界分发指南](fan-out-workflows.md)，实际成绩见[本批验收](../architecture/reviews/2026-11-10-fan-out-planning.md)。本批按源码／准确安装及所选真实服务的有限范围完成验收，原推荐包不自动包含它。

循环、共享可变状态 reducer 和逐记录流式 Workflow 仍不由此提供；Session／Turn、Coding、部署准入等组合继续按各后端已有契约选用或拒绝。框架与其他项目的当前能力对照见[2026-11-10 复核](../architecture/reviews/2026-11-10-framework-alignment.md)。

## 历史说明：dev15

以下保留 dev15 原文及当时支持／升级边界；其中“current”“Temporal refuses”等表述只说明该历史批次，不覆盖上方当前实现与验收。

The default local SDK needs no broker or database service. `DynamicWorkflowSpec`
keeps its original flat mode; opt into `plan_mode="dag"` for dependency plans.
`RuleDAGPlanner` is the default in that mode. `ModelDAGPlanner` delegates a
tool-free native child Run through the same budget/step limits and Provider.

```python
from relf_agent import AgentSpec, DynamicWorkflowSpec, DAGNode, DAGProposal, ValueRef


class ResearchPlanner:
    identity = {"kind": "research-planner", "version": "1"}

    async def plan(self, request, caller):
        return DAGProposal(
            [
                DAGNode("read", "reader"),
                DAGNode("answer", "writer", depends_on=("read",), input=ValueRef("read")),
            ],
            output=ValueRef("answer"),
        )


spec = DynamicWorkflowSpec(
    "research",
    {
        "reader": AgentSpec("reader", "Read evidence"),
        "writer": AgentSpec("writer", "Answer from confirmed evidence"),
    },
    plan_mode="dag",
    planner="research",
    child_budget=4,
    max_concurrency=2,
)
# Inject planners={"research": ResearchPlanner()} into the original LocalEngine.
# engine.submit(spec, input, command_id=..., budget=8); await engine.drive(run_id)
```

`PlanningRequest.capabilities` carries the registered member definitions;
`constraints` carries remaining steps, revisions, concurrency and credit limits.
A plan names registered members only. Each node has a stable ID, explicit
dependencies, typed input binding, optional `BranchCondition` and output Schema.
References must target input or a dependency ancestor. Cycles, undeclared members,
invalid conditions and incompatible output Schemas fail before dependent dispatch.
`Literal`, `ValueRef` and `InputMap` use the same binding validation as static graphs.
Independent ready nodes run up to the parent limit; this is bounded batch execution,
not streaming dataflow. Approval/unknown-effect branches pause and remain inspectable.

The parent commits the received proposal before adopting a revision, fixes each
node's bound input with child creation, and saves completed results. Crash recovery
uses accepted evidence instead of regenerating the plan or duplicating children.
`PlanningConclusion("refused", reason)` or `("needs_input", reason)` stops safely
with a structured result. This is a completed planning conclusion, not an interactive
`send_input` continuation protocol.

## Pending-node patches

`LocalEngine.patch_plan(run_id, DAGProposal(...), expected_plan_revision=0,
command_id="patch-1")` performs scoped command deduplication and revision CAS.
Diagnostics expose `workflow.plan_revision`, proposal digests and revision records.
Only active accepted DAGs can change. Dispatched, completed and skipped node
definitions are frozen, including dependencies and bindings. Pending nodes may be
added, removed or replaced within finite remaining limits. Replaying the original
command returns its receipt; a changed request conflicts. A patch is explicit host
control, not an unrecorded mutation by a planner.

## Nested members

Team and dynamic members accept `AgentSpec`, `WorkflowSpec` sequences,
`GraphWorkflowSpec`, `TeamSpec` and `DynamicWorkflowSpec`. Static graph nodes retain
their current Agent/Tool/Transform contract; arbitrary nested nodes are not added.
Every delegated workflow has its own Run and Session, links to its parent and pins
its own release plus the parent's release. Changes to ancestor configuration prevent
new dispatch by descendants. Parent cancellation/failure propagates to children.

The parent atomically reserves the child's entire credit cap before submission.
Recursive settlement charges actual descendant spend after completion; unresolved
effects retain conservative holds. Failure does not release the root Session while
a real descendant handler is still running. Execution depth defaults to a maximum
of eight, with `max_depth` available to tighten it. Definitions also have separate
limits of eight structural levels, 256 components and 1 MiB finite JSON.

```shell
relf init my-dag --template dag
cd my-dag
python -m agent_app --input hello --command-id first
relf --db .ralf/runs.sqlite --format text inspect RUN_ID
```

`--template nested` creates a DAG delegating to a team. Both packaged starters use
offline Echo/rule planning and require no model key. Runtime catalogs include
`dag-rule` and `dag-model` planner factories. Preserve original profiles and code
for recovery. Existing ten dev14 starter definitions and legacy flat serialization
remain unchanged; new nested/DAG parents need dev15. Temporal's current capability
subset refuses these definitions rather than routing them to local execution.

See [orchestration](orchestration.md), [static graphs](static-workflows.md) and
[planning evaluation](planning-evaluation.md) for related contracts and evidence.

Downgrading new nested records to dev14 is unsupported: the actual old wheel stops before dispatch, but its older definition reader may raise KeyError instead of a typed compatibility error. Keep dev15 for those Runs; legacy dev14 native/static/flat Runs are verified to continue under dev15.
