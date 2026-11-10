# 有界执行与结果检查

本批在 `085c0f5` 开发基线上新增显式 `BoundedLoopPolicy`：执行已有成员，检查已采纳结果，必要时进入下一轮；达到次数上限仍不满足条件则失败。本批按所选有限范围完成验收，准确候选和分层结果见[验收记录](../architecture/reviews/2026-11-10-bounded-loop.md)与[当前交付](current-delivery.md)。原推荐组合、Alpha、Fan-Out 包及历史制品不自动包含这项能力。

策略同时实现原 Planner／PlanVerifier 两个端口。每轮提出只有一个成员的原 DAG，由 Local／Temporal 原执行权威负责子 Run、权限、审批、预算、unknown 核验、取消和关闭。静态图继续拒绝环；这里没有新增循环图、共享状态 reducer 或执行后端。

## 先运行完整离线应用

[bounded_loop_workflow.py](../examples/bounded_loop_workflow.py) 使用可替换异步节点将数值逐轮加1，结果到3时停止。每轮都需要原审批，支持第二轮暂停、关闭重开及相同命令重放，不调用模型或网络。独立 SQLite 记录请求及效果回执；数学运算与审计不证明任意外部写恰好执行一次。

先安装包含本批实现的 SDK，再从对应源码或 sdist 取得示例。wheel 不包含 `examples/`。从源码目录复制并保留原脚本名：

```sh
BOUNDED_LOOP_DEMO_DIR="$(mktemp -d)"
cp examples/bounded_loop_workflow.py "$BOUNDED_LOOP_DEMO_DIR/"
cd "$BOUNDED_LOOP_DEMO_DIR"
python bounded_loop_workflow.py --db runs.sqlite --command-id repair-001 --pause-second-approval
python bounded_loop_workflow.py --db runs.sqlite --command-id repair-001
python bounded_loop_workflow.py --db runs.sqlite --command-id repair-001
```

第一条批准并完成首轮，在第二轮审批处暂停，累计业务请求为1。第二条沿原数据库继续审批，预期结果为 `{"done": true, "value": 3, "iteration": 3}`，本进程新增2次请求，累计请求和回执均为3。第三条找回原 Run 和回执，预期 `requests_this_process` 为0；以实际验收为准。

`runs.sqlite` 是原执行库，旁边的 `runs.sqlite.business.sqlite` 是示例自己的审计库。恢复时保留两个数据库、原脚本文件名及代码、组件 identity、定义、Profile 和 Scope；相同 command_id 保持原输入和配置。新业务操作使用新命令身份，旧任务保留匹配版本。省略 `--db` 会使用临时目录，适合一次运行；跨进程暂停与恢复使用上面的持久路径。

## 无模型的完整 SDK 组合

下面用默认 identity 节点原样返回每轮统一输入，以 `iteration == 2` 为停止条件。它只证明配置和两轮执行链路；次数标记不验证业务正确性。真实应用应换成受管理业务成员，并对其结果设置能反映实际完成条件的 Schema 和检查条件。

```python
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from relf_agent import (
    DynamicWorkflowSpec,
    GraphNode,
    GraphWorkflowSpec,
    RuntimeBuilder,
    RuntimeProfile,
    ValueRef,
)


async def main():
    loop_config = {
        "max_iterations": 2,
        "until": {
            "value": {
                "kind": "ref",
                "source": "input",
                "path": ["iteration"],
                "required": True,
                "default": None,
            },
            "equals": 2,
        },
    }
    profile = RuntimeProfile(
        "two-pass",
        "1",
        providers={},
        components={
            "workflow_executors": {"adapter": "identity", "config": {}},
            "planners": {"adapter": "bounded-loop", "config": loop_config},
            "plan_verifiers": {"adapter": "bounded-loop", "config": loop_config},
        },
    )
    member = GraphWorkflowSpec(
        "copy-iteration",
        [GraphNode("copy", executor="identity")],
        output=ValueRef("copy"),
    )
    workflow = DynamicWorkflowSpec(
        "two-pass",
        {"worker": member},
        planner="bounded-loop",
        verifier="bounded-loop",
        plan_mode="dag",
        child_budget=1,
        max_steps=2,
        max_revisions=2,
        max_concurrency=1,
        max_depth=3,
    )
    with TemporaryDirectory(prefix="relf-bounded-loop-") as directory:
        with RuntimeBuilder().build(profile, Path(directory) / "runs.sqlite") as runtime:
            handle = runtime.submit(
                workflow, {"ticket": "DEMO-1"}, command_id="two-pass-001", budget=2
            )
            done = await runtime.drive(handle.run_id)
            assert done.state == "succeeded", done.error
            assert done.result["iteration"] == 2
            assert done.result["previous"] == {
                "task": {"ticket": "DEMO-1"},
                "previous": None,
                "iteration": 1,
            }
            print(json.dumps(done.result, ensure_ascii=False))


asyncio.run(main())
```

临时目录退出后会清理执行库。需要重开时，使用明确保留的数据库路径和原代码／配置。`providers={}` 同时配合显式受管理节点；identity 工厂只接受空 config。替换节点沿用[结构化异步节点](managed-async-nodes.md)的注册端口、Schema、版本和资源所有权；Agent 成员仍需原 Provider。

## 双角色策略与数据约定

`BoundedLoopPolicy(worker="worker", *, until=None, max_iterations=3, version="1")` 是不可变配置。SDK 可以将同一个实例注入 `planners={"bounded-loop": loop}` 与 `plan_verifiers={"bounded-loop": loop}`；定义必须同时选择 `planner="bounded-loop"` 和 `verifier="bounded-loop"`。只选 Planner 时，原默认 `CompleteVerifier` 会在首轮完成，不提供这里的循环语义。配置工厂为两个角色各建纯实例，使用者保持两份配置与定义匹配。

每轮 Worker 接收：

```json
{"task": "原任务", "previous": "上一轮完整已采纳结果，首轮为 null", "iteration": 1}
```

`iteration` 从1开始。`previous` 是原结果的固定副本，保留完整 JSON，包括合法 null；下一轮不会读取未采纳、失败、待审批或 unknown 的子结果。成员输出没有新增强制信封格式。满足条件后，父 Run 返回最后一轮原结果；本策略不自动合并或摘要各轮结果。

| 参数 | 约定 |
| --- | --- |
| `worker` | 默认 `"worker"`，必须是定义中已有成员 alias |
| `until` | 默认检查最后结果的 `done == true`；可用原 `BranchCondition` 配置必需的 input 引用、有限 JSON 相等值和 negate |
| `max_iterations` | 严格整数1–32，默认3；至少执行一轮，不先检查原始任务 |
| `version` | 默认 `"1"`，非空字符串；与完整配置一起固定组件身份 |

`until` 在最后成员结果上解析，source 必须为 `input`，required 必须为 true，路径至多32段。比较沿用原 canonical JSON，布尔 true 与数字1不同；可以明确比较 null。缺少条件字段直接失败，不能当作“不满足”继续。条件满足只表示配置的检查成立，业务正确性取决于证据、Schema 和应用自己的判断。

最新结果满足条件则 `succeeded`；未满足且还有允许次数则沿原 `Verification("replan")` 推进修订；最后一次仍未满足则返回失败核验，包含 `reason="loop_iteration_limit"`、`iterations` 与 `last_result`。父 Run 必须失败，不把最后结果包装成成功；Local／Temporal 保留各自原有失败错误码。拒绝或补充输入的 `PlanningConclusion` 不是次数耗尽协议。

## 原限额、结果身份与恢复

`max_iterations` 是策略上限，原 `max_revisions`、累计 `max_steps`、子预算、宿主预算及嵌套深度仍可更严格。没有足够额度或下一步容量时沿原契约停止，不绕过授权或新一轮审批。若要容纳最多 N 轮单成员调用，基础定义可设置 `max_revisions=N`、`max_steps=N` 并配置足够预算；成员内部动作仍受其自身限制。已完成结果的核验不再预留新的步骤。

每轮仅提出固定 `iteration` 节点；实际跨轮子 Run、command、Action 与 effect 身份由原执行权威区分。策略只接收 `PlanningRequest`：Planner 的结果数等于 revision，Verifier 等于 revision＋1。每项是准确的 `{id, member, result}`；ID 为非空、有效 UTF-8、最多1024字符的唯一字符串，member 等于配置 Worker。

ID 是不透明身份。执行权威提供按轮次排序的已采纳结果，策略不根据 ID 拼写推断顺序，也不证明任意外来 history 的真实性。它会拒绝数量不符、重复 ID、其他成员，以及已经满足停止条件后仍追加的结果。调用身份与真实次序通过各后端执行／恢复测试独立核对。

Planner 和 Verifier 都不调用模型、工具或 caller，不保存循环状态。原 Store／History 保存提案、子结果和核验事实；恢复时纯 Verifier 可能重新计算，这不代表重新执行业务。图依赖环、跨轮直接节点引用、重复 Team 成员、任意共享可变 reducer 和逐记录流式 Workflow 继续按原限制处理，不能通过本策略绕过。

## JSON／TOML 入口

上面的 SDK Profile 已展示完整 JSON 组件结构。也可以保存下面的 Catalog 为 `loop.toml`，再用 `load_catalog("loop.toml").default` 替换示例中的 Profile，其余定义保持：

```toml
schema_version = 1
[default]
name = "two-pass"
version = "1"

[[profiles]]
name = "two-pass"
version = "1"
providers = {}

[profiles.components.workflow_executors]
adapter = "identity"
config = {}

[profiles.components.planners]
adapter = "bounded-loop"
[profiles.components.planners.config]
max_iterations = 2
[profiles.components.planners.config.until]
equals = 2
[profiles.components.planners.config.until.value]
kind = "ref"
source = "input"
path = ["iteration"]
required = true

[profiles.components.plan_verifiers]
adapter = "bounded-loop"
[profiles.components.plan_verifiers.config]
max_iterations = 2
[profiles.components.plan_verifiers.config.until]
equals = 2
[profiles.components.plan_verifiers.config.until.value]
kind = "ref"
source = "input"
path = ["iteration"]
required = true
```

适配器名均为 `bounded-loop`，角色键为 `planners` 和 `plan_verifiers`。until 的 value 使用原 ref binding，equals 必须显式存在，negate 可省略；不支持函数表达式或未知字段。同步／异步 SDK 装配沿[Runtime 配置](runtime-assembly.md)和[资源生命周期](async-assembly.md)，工厂不创建客户端或新 owner。

Temporal 使用原 `TemporalRuntimeBuilder.abuild`，Catalog 的 kind 为 `temporal-profiles`，见[Temporal Profile](temporal-profiles.md)。显式选择同样的两个角色，继续由原 Parent History 执行；无模型 Graph 组合遵守[Temporal 受管理节点](temporal-managed-nodes.md)现有 stateless 范围，不扩大 Session／Turn、Coding、部署准入或 parent completion 组合支持。

本批源码／准确安装同692项、各2项真实Temporal、15条纯运行依赖及同输入完整离线已通过；首Python块及完整审批应用在checkout外执行通过。首轮Service因预算字段夹具错误的两失败／0 History保留；修正后源码快照与最终1596输入完全一致，不改产品或期限。真实服务仅覆盖三轮收敛与第二轮审批静止窗口的Worker重启，不授予活跃物理handler全冷恢复或未运行的平台资格。冻结候选与分层结果以独立验收为准，不把原包或推荐组合升级为新能力。原失败和历史成绩保留，本批不推送或公开发布，也不授予完整 R01–R26、真实模型质量、外部采用或跨框架对等资格。
