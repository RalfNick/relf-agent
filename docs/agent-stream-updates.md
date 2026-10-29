# 统一模型与工具增量流

本页针对 `19dcc60` 后的维护源码，原 a8 两包没有这些 API。先使用当前源码或独立私有验证包；本批不准备新 Alpha、不推送或公开发布。

第一批按用户新目标冻结为生命周期／事件／增量流单一主线，唯一推荐私有版本、运行命令和门槛见[交付清单](../architecture/reviews/2026-10-29-stream-batch-freeze.md)。原 `0.1.0a8` 包不包含这些 API。

`AgentRun.stream_updates()` 把原持久事件订阅投影为 `AgentStreamEvent`，同时展示模型文本、显式异步工具进度和原权威事实。Local 仍由原 Coordinator／Store 提交；Temporal 仍由原 Workflow／History 接收。它不是新的执行引擎，也不是逐记录 Workflow 数据流。

## 默认关闭，显式启用

独立应用可在原 `Agent` 入口直接选择策略，不必先装配 Engine：

```python
from relf_agent import Agent, StreamedModelProvider, StreamUpdatePolicy

async with Agent(
    model=StreamedModelProvider(base_provider),
    tools=tools,
    stream_updates=StreamUpdatePolicy(),
    db_path=".ralf/runs.sqlite",
) as agent:
    handle = await agent.submit("业务请求", command_id="request-001")
    # 用下方 stream_updates 消费方式观察。
```

共享 Runtime 的 Agent 沿用宿主固定策略，不能在 Agent 构造时覆盖它。需要明确资源装配时使用原 Engine／Runtime：

```python
from contextlib import aclosing
from relf_agent import (
    LocalEngine, Runtime, SQLiteStore, StreamedModelProvider, StreamUpdatePolicy,
)

# base_provider 是已配置好的既有 Provider，tools 是原 ToolRegistry。
model = StreamedModelProvider(base_provider, chunk_chars=128)
engine = LocalEngine(
    SQLiteStore(".ralf/runs.sqlite"),
    providers={"default": model},
    tools=tools,
    stream_updates=StreamUpdatePolicy(),
)
try:
    async with Runtime(engine, owned=True) as runtime:
        agent = runtime.create_agent(spec)  # 原 AgentSpec／Workflow 定义
        handle = await agent.submit("业务请求", command_id="request-001")
        async with aclosing(handle.stream_updates()) as updates:
            async for event in updates:
                print(event.kind, event.authoritative, event.data)
                last_cursor = event.cursor.token
        print(await handle.status())
finally:
    # 正常迭代自动关闭；自定义迭代器的失败清理保留在 wrapper 中。
    await model.retry_stream_closes()
```

`StreamedModelProvider` 只发出一次底层 `stream` 调用，不调用 `complete` 后再重试流式接口。它只接受实际可关闭的 AsyncIterator，完整响应在 EOF 且没有额外事件后才交还 Engine；半成品文本不产生工具提案。不支持流式端口的 Provider 在构造时拒绝，不静默降级。能力与模型续接沿用原 Provider；具体线上型号仍需独立验证。

`chunk_chars=1..256` 控制文本合并，默认128字符；小于阈值的末尾文本随完整响应到达时发出。展示停用或达到限额后停止拆分剩余文本，但继续完整消费、校验响应。预算沿用模型／工具实际尝试，增量不额外预留 execution credits。

`stream_updates=None` 为默认值，不改变原 Manifest 或新增展示事件。显式策略固定在新 Run 的 Release；更改策略不能用于继续旧配置的 Run。首批提供 SDK 注入，未增加 JSON／TOML 内置声明工厂；可通过原宿主工厂组合，不在 Profile 中导入代码。

## 异步工具显式报告

```python
from relf_agent import emit_tool_delta

@tools.tool(effect="read_only")
async def lookup(order_id: str):
    await emit_tool_delta({"message": "开始查询"})
    result = await business_api.lookup(order_id)
    await emit_tool_delta({"message": "查询返回"})
    return result
```

工具注册、参数校验、授权、审批、效果类别和核验方式仍须按[工具 SDK](sdk-model-tools.md)配置。`emit_tool_delta` 只在框架持有的原异步工具 Attempt 内报告；无上下文、已结束的上下文或展示停用时返回 False。False 不是业务失败／未发送证明，不能据此重执行业务操作。

首批不截获同步工具、CLI、MCP 或 Coding Runner 的任意 stdout，也不自动公开模型 reasoning 或未完成的工具参数。同步工具仍提供原派发／回执事实；异步工具也需要显式调用。进度由工具作者提供，声称“已写入”不能替代原效果回执。

## 类型、限额与取消

| kind | 含义 | authoritative |
| --- | --- | --- |
| `model_delta` | 未验证的模型文本前缀，data.text | False |
| `tool_delta` | 工具显式 JSON 进度 | False |
| `gap` | 达到条数／字节限额，或检测到传输序号间隙；展示不完整 | False |
| `model_end`／`tool_end` | 原权威已经记录响应／回执，或未知结果事实；source_kind 说明具体事实 | True |
| `run` | 其他原 Run 事实，保留 source_kind | True |

`authoritative=True` 只表明对应事实由原权威记录。模型响应可能随后被拒绝；未知结果、取消或“收到回执”不等于 Run 成功，也不单独证明所有远端处理器停止。最终结果应读取 `handle.status()`。工具已核验效果仍以原 Action 日志为准。

记录含原 EventCursor；增量还含 Action／Attempt 和每 Attempt 的 sequence。`event.data` 返回副本，`event.to_dict()` 提供完整原事件来源。上下文压缩、记忆提炼等辅助调用没有隐式套用业务 Attempt 的展示身份。

默认每 Attempt 最多64条 delta、64KiB payload 合计、单条4KiB；范围分别为1..1024、256B..1MiB、256B..64KiB，单条限额不得高于合计。超限只记录一个 gap 并停止后续展示，完整响应仍走原接收／采纳。非法 JSON 产生固定 gap 原因，不运行嵌套协程；无效对象由生产方处置。

`publish_timeout` 默认0.25秒、范围大于0且不超过2秒，用于可取消的异步发布；固定 SDK Signal 超时／失败后不重试展示，后续进度停用，结束事实里的 `stream_end.observation` 标注截断原因。它不是磁盘操作的硬实时保证，也不是业务 deadline。慢消费者读取持久事件，消费速度不会成为工具执行的队列条件；这不提供无限历史容量，仍需原保留治理。

取消 `anext()`、结束迭代、观察超时或 `aclose()` 都只停止当前订阅。它们不提交业务取消，不关闭借用的 Runtime／Worker，不隐式 resume；Runtime 排空或关闭后，缓冲记录也拒绝发送。业务取消仍调用原 `handle.cancel(command_id=...)`。

一个订阅只允许一个消费者。并发的第二次 `anext()` 返回 `ValidationError`，不会关闭第一次正常读取，也不推进游标。需要多个独立观察者时分别创建订阅；每个订阅使用自己的最后有效游标。

## 重连、恢复与关闭失败

```python
from relf_agent import EventCursor

# 重开原 Runtime 后先 attach 原 RunRef；有停顿时显式使用原控制命令。
async with aclosing(handle.stream_updates(
    after=EventCursor.from_token(last_cursor), follow=False
)) as updates:
    for_replay = [event async for event in updates]
```

`after`、分页、`follow`、读取期限和条数限额与[原事件订阅](agent-api.md#subscribe-without-assembling-another-engine-adapter)相同。只有成功交付的类型化记录推进对外游标；协议校验失败保留最后有效游标并关闭订阅，修复来源后新建订阅。`follow=True` 会继续等待审批／用户输入，观察总体期限请结合 `asyncio.timeout` 和 `aclosing`。

这不是 token 断点续传：模型／工具完整响应未被保存时，仍遵循原未知结果、核验和重试规则。已经保存的响应／回执恢复时不重调模型或 handler；旧展示从原日志重放。进度消失或不完整不能授权重新执行写操作。

包装器自动关闭它创建并消费的迭代器，底层 Provider／客户端仍借用。EOF 后普通关闭失败不抹去已完成 ModelResponse；`pending_stream_closes` 保留数量，`retry_stream_closes()` 显式重试这些迭代器，不关闭底层 Provider。清理未完成时拒绝新的 dispatch；活动流尚未排空时拒绝清理重试，不取消业务流。真正取消源调用仍传播 CancelledError，并保留失败清理责任。日志仅给固定关闭错误码；自定义迭代器须支持幂等关闭。直接调用 wrapper.stream 时，返回迭代器由调用方管理。

取消恰好发生在迭代器的 `aclose()` 等待期间时，也会传播取消并保留清理句柄。应先按原 Runtime 的关闭／排空规则处理活动调用，再显式重试 `retry_stream_closes()`；成功后重复清理不再调用旧迭代器。后续维护的反例与验证见[观察边界记录](../architecture/reviews/2026-10-29-stream-observation-boundaries.md)。

## Temporal

```python
runtime = TemporalRuntime(
    providers={"default": StreamedModelProvider(base_provider)},
    tools=tools,
    stream_updates=StreamUpdatePolicy(),
)
# 按原 Worker 注册／发布／客户端 Runtime 流程部署该新 Release。
```

固定 Activities 在原 Attempt 上下文内发出 Signal，捕获原 Client、namespace、Workflow id 和执行 epoch。原 Workflow 校验 Scope、Release、Action、Attempt、序号与容量，重复不追加，乱序／遗漏有 gap，展示事件不推进业务 revision 或预算。非法 Signal 不使 Workflow Task 失败。结束事实根据实际记录数与发布观察标注不完整；Signal 发送成功不等于它已成为业务效果回执。

Workflow 重放仍由 History 驱动，模型完整响应、工具 Journal、审批、实际执行结束和取消仍使用原协议。旧 Manifest 不选择此功能，旧 History 不自动迁移；新 Worker／Release 需要一起部署。客户端 `stream_updates()` 继续复用原身份校验和查询；取消客户端订阅不取消 Worker Activity。

前批验证覆盖 Local 真实 SQLite 关闭重开、重复审批与一次效果、Temporal 纯状态／模拟 Signal、真实 SDK 活动装配和沙箱，见[原记录](../architecture/reviews/2026-10-29-agent-stream-updates.md)。后续追加原生文本 Agent 的真实 Service：前缀与观察取消、审批去重、限额gap、等待审批时Worker进程重启及History重放，源码／目录外安装各3项通过，见[Service验收](../architecture/reviews/2026-10-29-temporal-stream-service.md)。工具为只读lookup，不证明真实写效果或模型质量。

客户端和Worker应从同一个固定模块导入Provider／工具工厂。流包装器会固定Python入口的模块／函数／代码身份；如果客户端从业务模块导入，而Worker以`__main__`重新声明同一类，二者Release不同，应修正装配入口，不能放松身份校验后继续原Run。

高级组合增量流、在途Activity被杀、响应／回执接收与采纳之间的Service故障窗口、真实写／Journal、线上模型与平台矩阵仍未验收；不套用上述子集、旧S2或a8成绩。

在维护源码checkout安装可选Temporal／开发依赖后，可用一个新的本机Service复验。先在独立终端启动固定CLI，使用全新数据目录与空闲端口：

```sh
RELF_STREAM_TEST_DIR="$(mktemp -d)"
temporal server start-dev --headless --ip 127.0.0.1 --port 7323 \
  --db-filename "$RELF_STREAM_TEST_DIR/server.sqlite"
```

再在仓库目录执行：

```sh
RALF_TEST_TEMPORAL_ADDRESS=127.0.0.1:7323 python -m pytest \
  tests/test_temporal_stream_service.py -q -W error
```

三个测试各建独立队列／Scope，测试结束会停止自有Worker；完成后在第一终端停止自己启动的Service。没有设置测试地址时三项按条件跳过。不要指向业务Service或把跳过计为真实后端通过；本批实际版本和完整安装复验见上述Service记录。

## 离线示例

从维护源码复制 [stream_updates.py](../examples/stream_updates.py) 到安装 SDK 的独立目录，运行两次：

```sh
python stream_updates.py --db .ralf/stream-example.sqlite --command-id example-1
python stream_updates.py --db .ralf/stream-example.sqlite --command-id example-1
```

首次两次模型、一次只读工具；第二次找回相同 Run 和事件，实际模型／工具调用均为0。示例不依赖模型凭据或网络。真实模型按[模型适配](model-adapters.md)配置并显式选择该包装器；成功运行离线示例不证明模型质量。
