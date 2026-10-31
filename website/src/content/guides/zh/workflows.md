---
title: 工作流与多 Agent
description: 从静态图到有界的 Plan 与 Team，按任务需要选择编排方式。
locale: zh
slug: workflows
sources: [docs/static-workflows.md, docs/orchestration.md, docs/parallel-workflows.md, docs/dynamic-dag.md, docs/concepts.md, docs/user-input.md, docs/managed-tools.md, docs/runtime-assembly.md]
---

## 先选择任务结构

| 结构 | 适合的任务 |
| --- | --- |
| 单 `AgentSpec` | 一个模型与工具循环 |
| `WorkflowSpec` / 静态图 | 已知步骤、依赖、分支与输入映射 |
| `TeamSpec` | 注册成员之间的顺序、路由或监督协作 |
| `DynamicWorkflowSpec` | 在明确成员与次数上限内规划、执行、验证与重规划 |

先从最小结构开始。子 Run 继续遵循原有工具、审批、预算与效果恢复协议。

## 运行一个静态图

安装 SDK 后，选择一个不存在的目录：

```bash
relf init my-graph --template graph
cd my-graph
python -m agent_app --input urgent --command-id urgent-task
```

`graph.json` 定义依赖、分支和结果映射，`runtime.toml` 定义 Provider 与版本。模板使用离线回显；它验证执行与装配链路，不代表模型任务质量。

保存提交、稍后继续的方式：

```bash
python -m agent_app --input urgent --command-id queued-task --submit-only
relf --config runtime.toml resume RUN_ID
relf --config runtime.toml --format text inspect RUN_ID
```

静态图支持显式依赖、条件、输入映射和合并；有界并行需要显式配置 `max_concurrency`。纯 Transform 只做 JSON 数据计算，外部 I/O 使用受管理工具。完整定义见[静态图指南](repo:docs/static-workflows.md)。

## 不需要模型时，直接运行 async Tool 流程

固定维护源码的 graph 模板还生成一个独立的订单／库存工具应用。从一个可写工作目录开始，选择不存在的目标：

```bash
relf --format text init ../my-tool-flow --template graph
cd ../my-tool-flow
python -m agent_app.tool_graph --order-id ORD-1 --command-id order-1
python -m agent_app.tool_graph --order-id ORD-1 --command-id order-1
```

两次应得到相同 `run_id` 和结果；`model_actions=0`、`tool_actions=2`、`credits_spent=2`。`lookup → stock` 是两个只读 async Python 工具，结果包含订单、SKU 和可用性。新订单使用新命令 ID；这不是实际网络调用或写入效果证明。

先仅提交另一个订单：

```bash
python -m agent_app.tool_graph --order-id ORD-2 --command-id order-2 --submit-only
```

将 `RUN_ID` 换成上条返回的实际 ID，再检查、恢复并确认 `succeeded`：

```bash
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine --format text inspect RUN_ID
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine resume RUN_ID
relf --db .ralf/tool-graph.sqlite --format text inspect RUN_ID
```

`tool-runtime.toml` 显式声明 `providers = {}`，`tool-graph.json` 定义节点和映射，`agent_app/tool_runtime.py` 注册 `order-fixture` 及原恢复工厂。替换其中两个 async 函数即可接自己的业务；同步注册工厂只装配工具，异步客户端按[异步装配](repo:docs/async-assembly.md)管理，不能返回未等待的 coroutine。

空 Provider 只适用于有限 **Local Tool／Transform 图**，字段仍必填。普通 Agent／混合图需要可解析的 Provider，TemporalProfile 仍要求非空配置。Tool 节点复用原 Action、预算、授权、审批、回执和未知效果核验；不是任意节点／reducer 或逐记录数据流。原 a8 包没有这些生成文件。

### 给新工具流程加审批

从上面的 `my-tool-flow` 目录执行。只在新项目首次提交前改配置，不改写旧 Run 的 Profile：

```bash
relf --format text init ../approved-tool-flow --template graph
cd ../approved-tool-flow
python -c 'from pathlib import Path; p=Path("tool-runtime.toml"); p.write_text(p.read_text().replace("requires_approval = false", "requires_approval = true"))'
python -m agent_app.tool_graph --order-id ORD-3 --command-id order-3
```

首次停在 `waiting_approval`：已创建第一个 Tool Action（`tool_actions=1`），但尚未派发，`credits_spent=0`。这里的 Action 数不等于实际 handler 调用数。用返回的 Run ID 检查提案，从 pending 取 `ACTION_ID`／`OPERATION_DIGEST`，为每项决定选择自己的稳定 `DECISION_ID`：

```bash
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine --format text inspect RUN_ID
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine approve RUN_ID ACTION_ID --digest OPERATION_DIGEST --command-id DECISION_ID
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine resume RUN_ID
relf --db .ralf/tool-graph.sqlite --format text inspect RUN_ID
```

第一个节点批准后，resume 可能停在第二个节点审批；重新检查新的 Action／digest，换一个决定 ID，再执行上述控制步骤，直到 Snapshot 为 `succeeded`。重试同一批准使用原 ID，只回读原回执，不增加调用；最终仍为两个 Tool Action、0 个 Model Action、2 credits。此例对只读工具演示审批；改成写操作时另行声明真实效果类别、下游幂等／查询与核验契约。

## 定义一个团队

下面的例子用离线 Provider 理解成员委派，无需模型密钥：

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

Team 的默认策略包括 `sequential`、`router` 与 `supervisor`。每个成员可以选择自己的模型、工具与输出约束；父级保留委派身份与子 Run 链接。

## 动态规划也需要边界

Plan 通过已注册的 Planner 与 Verifier 提出有限步骤。配置允许成员、`max_revisions`、`max_steps`、`max_concurrency` 与子预算。规划只是提案，执行事实仍由引擎提交。

并非每种后端都支持所有嵌套组合。支持范围与配置细节见[编排指南](repo:docs/orchestration.md)。

## 把业务步骤放在合适的节点

以工单为例，先读取信息和检索手册，再诊断；只有满足变更条件才进入写工具，最后检查回执并汇总答复。已知依赖与条件可直接表达为静态图，不必每次重新规划流程。

| 节点职责 | 选择 | 执行要点 |
| --- | --- | --- |
| 解释输入、使用工具、生成结论 | Agent 节点 | 模型、允许工具、输出和预算按定义固定 |
| 明确调用外部业务能力 | Tool 节点 | 保存 Action、审批与回执，不额外制造模型调用 |
| 字段投影、JSON 合并等计算 | Transform 节点 | 同步纯计算，不隐藏网络或数据库 I/O |

这些是 Local 图的节点选择；Temporal 不支持所有相同节点和组合。节点输出通过显式映射交给后继，不能只依赖模型聊天中提到的结果。

## 理解团队策略与计划修订

| 策略 | 如何协作 | 常见用途 |
| --- | --- | --- |
| `sequential` | 按成员顺序传递任务及已保存结果 | 研究后复核、诊断后整理答复 |
| `router` | 根据配置路由字段选择注册成员 | 按业务类型分派专家 |
| `supervisor` | 有限并行 worker 后由指定 supervisor 汇总 | 收集独立分析，再形成结论 |

路由、角色、并发和预算都显式配置。成员名称不授予额外工具权限，成员同意也不会自动批准其他成员的写操作。

需要 DAG 或嵌套成员时，使用对应定义及已支持子集。计划修订创建新的逻辑调用，不改写原已完成结果、效果或批准。业务未完成时由显式 Verifier 提出后续步骤，并继续受次数与预算限制。

## 并行、预算与人工暂停

`max_concurrency` 限制并发委派，父预算约束整个任务，子预算在委派时预留。等待恢复、效果未知或实际调用未停止的孩子，仍可能占用容量和额度，不能换 ID 绕过。

父子 Run 分别可观察。孩子需要审批时，先检查实际子 Run 的 pending、原 Action 与摘要，处理原批准或核验，再推进父任务。取消父任务不证明下游业务已回滚。

只并行独立分支；依赖前一步结果的任务通过图边表达次序。细节见[有界并行](repo:docs/parallel-workflows.md)。

## 恢复与部署

恢复消费原计划、委派身份与已保存结果。对实际子 Run 审批或核验后，再驱动原父 Run。取消停止后续派发，不自动回滚业务效果。

Local 使用原本地执行存储。Temporal 使用独立的 Worker、发布与执行配置，以原 Workflow History 为权威；本地成功不代表分布式组合已经验证。准备部署时阅读[Temporal 执行指南](repo:docs/temporal-execution.md)及当前支持矩阵。

子任务等待用户输入时，从 `root.pending()` 定位问题实际所属 RunRef 并向它回复，见[持久输入](/zh/docs/user-input/)。默认 wait 可能在根仍为 `running` 时报告 `control_available`，应根据 pending 证据选择控制。完整顺序应用见[连续应用教程](/zh/docs/app-tutorial/)，修改后按[测试与评估](/zh/docs/testing/)验证。
