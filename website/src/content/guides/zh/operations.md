---
title: 运行与部署
description: 选择 Local 或 Temporal，管理版本化配置、执行额度、观察与资源生命周期。
locale: zh
slug: operations
sources: [docs/runtime-assembly.md, docs/agent-api.md, docs/agent-limits.md, docs/temporal-execution.md, docs/recovery-guide.md, docs/agent-stream-updates.md]
---

## 先选择执行后端

| 维度 | Local | Temporal |
| --- | --- | --- |
| 执行权威 | 原本地执行存储与 Coordinator | 原 Workflow History |
| 起步依赖 | Python、本地 SQLite 与应用工厂 | 显式 Temporal Service、Worker、任务队列与发布配置 |
| 推进方式 | `drive` 或托管 Runtime 推进原 Run | Service／Worker 执行；Facade 发送控制并观察进度 |
| 恢复依据 | 原数据库、工厂、组件版本与业务证据 | 原 History、匹配发布、队列及业务效果证据 |
| 适用起点 | 本地工具助手、开发试点和低依赖流程 | 需要独立 Worker 的所选分布式组合 |

Local 不会自动变成分布式调度器；Temporal 也不是把 LocalEngine 放进 Activity。两者共享部分公共概念，但功能、会话、工具节点及嵌套组合并不完全对等。Temporal 在当前 Alpha 中按实验性范围显式配置，使用前阅读[Temporal 指南](repo:docs/temporal-execution.md)和[当前支持状态](repo:docs/implementation-status.md)。

官网是静态网站，可以由 Cloudflare 托管；Python Agent 应用需要自己的 Python 执行环境或 Worker。托管官网不会启动 Python Agent 或提供 Temporal Service。

## 用一个 Profile 管理组件

已经完成源码安装后，在新目录生成离线配置项目：

```bash
relf init my-config-agent --template config
cd my-config-agent
python -m agent_app --input hello --command-id hello-1
python -m agent_app --input pending --command-id pending-1 --submit-only
relf --config runtime.toml --format text inspect RUN_ID
relf --config runtime.toml resume RUN_ID
```

将 `RUN_ID` 换成第二次提交返回值。`runtime.toml` 定义运行组件，`agent.toml` 定义 Agent。模板 Provider 为 `offline-echo`，只验证装配与执行。

一个基础 Profile 的形状如下；模板已经包含可编辑的完整配置：

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

配置只选择已注册组件，不执行 Python 或动态导入任意插件。相对资源路径以配置文件目录解析；跨目录恢复时保留同一绝对数据库与配置路径，并确保原工厂可导入。需要异步资源构造时使用对应异步装配入口。

## 改配置与恢复旧任务

Profile 的 `name/version` 对应不可覆盖的配置身份。切换 default 只影响新任务；旧 Run 按原 Profile 解析。保留原声明、适配器实现与数据，Catalog 不会替你归档代码或迁移数据库。

同一命令 ID 与相同请求回读原任务；相同 ID 改输入产生冲突。想用新配置执行新任务，使用新命令 ID。`definition_mismatch` 应恢复原版本，不能通过宽松默认值或改别名绕过。

## 额度、限制与完成验证

| 机制 | 控制什么 | 不能由此推断什么 |
| --- | --- | --- |
| Run `budget` | 以整数 execution credits 预留、结算执行尝试 | 货币预算、精确 Token 或供应商费用硬上限 |
| Agent 限制 | 决策数、上下文字符、独立工具 Action 数等上限 | 整个宿主的 CPU、并发、速率或实际远端停止 |
| 图／Plan 限制 | 步骤、修订、并发与子预算 | 任意规模都能执行或一定规划正确 |
| 输出 Schema / Verifier | 输出结构及显式业务完成条件 | 模型文本天然真实、工具回包等于业务成功 |

有效 Agent 上限取 Spec、宿主与所选策略的约束。纯限制策略不能做 I/O 或扩大权限；恢复既有 Action 也不代表创建新的独立工具动作槽位。限制身份与原任务一起固定。

## 观察、控制与服务关闭

`status`、`events`、`inspect` 和 `attach` 用于观察。等待结束可能是暂停或观察超时，先检查 snapshot 的实际状态；需要恢复时显式 `resume`，需要取消时提交独立取消命令。

关闭应用时，先停止新任务准入，完成或取消并等待自己的执行任务，再关闭自己拥有的客户端和数据连接。直接注入的借用组件由其所有者关闭；不能在工具线程、子进程或远端写效果仍未知时，假设 Python await 取消已经完成资源收尾。

备份要覆盖执行记录、所选 Session／Facts／Knowledge／Artifact 数据，以及业务效果证据；只复制一个空闲数据库文件不等于完整应用恢复。具体步骤见[恢复指南](repo:docs/recovery-guide.md)。

## 用 Agent 观察事件并重连

在安装了固定维护源码的独立目录中，保存为 `observe_agent.py`，执行 `python observe_agent.py`。这是无密钥、无外部服务的完整例子：提交后等待、先读一条持久事件，再从已交付游标继续，关闭后在原数据库重连。

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

两条输出都应为 `succeeded` 且 `run_id` 相同，第一条还有 `cursor_resumed=true`，第二条有 `reconnected=true`。重复脚本找回原请求；保存 `RunRef` 不等于保存数据库或认证凭据。这里只重连已完成 Run；排队或暂停任务需要原配置下显式 resume／审批／回复输入，attach 不会自动执行。

`subscribe_events()` 直接返回订阅，使用 `aclosing`；`follow=True` 会穿过人工暂停继续等待，有限历史读取用 `follow=False`。只保存已成功交付记录的 `.cursor.token`，不要用原始 seq 替代带 Scope／Run 身份的重连 token。`read_timeout` 限制一次读取；整体期限用 `asyncio.timeout` 包住消费。关闭、取消或观察超时不取消业务，也不关闭借用的 Runtime。

## 显式展示模型文本与异步工具进度

回到安装所用的**固定框架源码根目录**，虚拟环境保持激活，选择不存在的 `../stream-app`：

```bash
mkdir ../stream-app
git show 300c62ce8dd417df6b471ce1c10a1b7a562d2c46:examples/stream_updates.py > ../stream-app/stream_updates.py
cd ../stream-app
python stream_updates.py --db .ralf/stream-example.sqlite --command-id stream-1
python stream_updates.py --db .ralf/stream-example.sqlite --command-id stream-1
```

首次末条 JSON 应为 `succeeded`、`model_calls=2`、`tool_calls=1`；第二次读取同一 Run 和原事件，实际两种调用均为 0。示例完全离线，真实模型另行选择适配器与凭据。这是从固定源码复制的应用示例，不要求把仓库 `examples` 包加入 Python 导入路径。

示例在新 Run 上显式选择 `StreamUpdatePolicy()`，模型包装为 `StreamedModelProvider(base, chunk_chars=8)`，async 工具显式调用 `emit_tool_delta(...)`；普通 Agent 可在构造时传 `stream_updates`。共享 Agent 沿用 Runtime 策略。默认关闭，改变策略要使用新的配置和请求身份。

| 事件 | 该怎样理解 |
| --- | --- |
| `model_delta`／`tool_delta` | 非权威文本／JSON 进度，只用于展示 |
| `gap` | 非权威的截断或传输间隙提示；不保证展示完整 |
| `model_end`／`tool_end` | 对应原响应、工具回执或未知结果事实已记录，不等于 Run 成功或远端处理器全部结束 |
| `run` | 原 Run 的其他持久事实；最终检查 `handle.status()`、Action 和效果证据 |

默认每 Attempt 最多 64 条 delta、合计 64 KiB、每条 4 KiB；达到限额只记一个 gap 并停止后续展示，原完整响应仍继续校验与采纳。不是无限历史存储、模型 reasoning、任意 stdout 捕获或 Workflow 节点数据流。订阅取消仍只停止观察；需要业务取消时显式调用原 handle 的 `cancel(command_id=...)`。

完整响应只在流 EOF 且验证结束后返回，半成品文本不能派发工具。包装器借用底层 Provider；先按原 Runtime 规则排空活动调用，若自定义迭代器关闭失败，检查 `pending_stream_closes` 并显式 `await model.retry_stream_closes()`，不能遗失原清理责任。每个订阅只允许一个消费者；多个观察者分别创建订阅并保留各自游标。

Temporal 沿原 History／Worker 接收 Signal，已验收仅覆盖所选原生文本 Agent Service 子集；本页离线例子不新增 Temporal 高级流组合、真实写、线上模型或平台资格。具体边界见[增量流说明](repo:docs/agent-stream-updates.md)。

## 从本地试点继续

先验证一个离线任务、真实工具和审批恢复，再为实际模型、外部数据、MCP 或 Temporal 添加所需依赖与服务。Temporal 可选依赖从源码仓库根目录安装 `python -m pip install -e '.[temporal]'`，随后自行配置 Service、Worker 与匹配发布；本指南不会隐式启动服务。

API 和部分组合仍在 Alpha 阶段。部署判断使用你的实际组件与故障场景证据，当前资格见[实现清单](repo:docs/implementation-status.md)。遇到执行问题，从[审批与恢复](/zh/docs/recovery/)按状态定位下一步。

## 验证基线与支持边界

本站基于页首所示固定源码提交的 SDK **0.1.0a8 基版本维护源码**，验证日期 **2026-10-31**。日期记录这些教程的验证，不表示每种部署或线上型号均获保证。

| 组合 | 文档状态 | 使用前继续验证 |
| --- | --- | --- |
| Local＋SQLite＋离线模型／工具 | 教程基线 | 运行快速开始和应用测试 |
| Local Session、持久输入、词法／混合检索、显式 Facts | 提供离线操作路径 | 使用自己的案例运行连续应用和输入教程 |
| 真实模型、Embedding 和外部工具 | 显式适配器与配置 | 检查具体端点、权限、错误、关闭与业务结果 |
| 远程存储或 Temporal Worker／Release | 实验性支持子集 | 按所选后端指南逐项验收；本站教程未验证这些服务组合 |

方法签名查 [API 与 CLI 参考](/zh/docs/api-reference/)，暂停交互看[持久用户输入](/zh/docs/user-input/)，切换 Provider 或部署前运行[测试与评估](/zh/docs/testing/)。固定技术源说明该快照的范围；仓库后续开发不会改变旧 Run 恢复所需的原配置。
