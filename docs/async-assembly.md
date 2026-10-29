# 异步组件装配与客户端生命周期

dev13 提供 AsyncLifecycle、register_async、abuild、own_async 和 RuntimeInstance.aclose。它们用于组件创建与资源清理；LocalEngine 事务、Store.close、Coordinator acquire/release 仍同步完成。默认 build/close 继续可用。

## 从安装包开始

```shell
relf --format text init my-async-agent --template async
cd my-async-agent
python -m agent_app --input hello --command-id first
python -m agent_app --input hello --command-id first
```

相同 command_id、定义和输入返回原回执；不同输入使用新 command_id。模板使用真实 httpx.AsyncClient 和离线 MockTransport，无网络请求或模型费用。它验证 SDK 装配/清理，不代表 AI 任务表现。

```shell
python -m agent_app --input hello --command-id queued --submit-only
python -m agent_app --resume RUN_ID
relf --db .ralf/runs.sqlite --format text inspect RUN_ID
```

runtime.toml 声明 Profile；provider_factory 注册 async-demo，调用 context.own_async(client) 后返回 Provider。create_runtime 根据原 Run 身份选择保留的 Profile；更改 default 只影响新任务。替换 transport/工厂接入真实模型时，显式配置服务与凭据并更新版本；原代码和声明仍需保留。

## SDK 与配置工厂

register_async 显式注册 async 函数、bound method、partial 或 async callable。validator 保持纯同步并返回 None；JSON/TOML 只选择注册名，不执行 Python。abuild 接受既有同步工厂；同步工厂返回 awaitable 不会被隐式等待。

```python
import asyncio

from relf_agent import AgentSpec, ComponentRegistry, ModelResponse, RuntimeBuilder, RuntimeProfile


class Client:
    async def aclose(self):
        pass


class Provider:
    identity = {"kind": "async-example", "version": "1"}

    async def complete(self, messages, tools):
        return ModelResponse(output="offline example")


async def factory(config, context):
    context.own_async(Client())
    return Provider()


async def application():
    registry = ComponentRegistry()
    registry.register_async("provider", "my-async-provider", factory)
    profile = RuntimeProfile("app", "1", {"default": {"adapter": "my-async-provider"}})
    async with await RuntimeBuilder(registry).abuild(profile, ".ralf/async.sqlite") as runtime:
        handle = runtime.submit(AgentSpec("assistant", "Answer"), "hello", command_id="first")
        return await runtime.drive(handle.run_id)


if __name__ == "__main__":
    print(asyncio.run(application()))
```

own 管理同步 close；own_async 管理 async aclose。在开放的登记阶段，同对象同模式去重，切换模式拒绝；未登记资源仍由应用/工厂管理。Store 属于执行权威，不能 own_async(Store)。Factory 为本次实例创建 owned 资源，不应让两个 Runtime 同时拥有同一客户端/Store。

资源台账开始实际清理后，`own`／`own_async` 拒绝新的资源登记；这一边界在清理失败、取消外层等待和清理完成后都保持，共享 Context 也遵守原持有者的状态。不要在资源关闭回调中登记新客户端；登记被拒绝时，对象仍由创建方负责关闭。仅因同步清理方式不匹配而被前置拒绝时，尚未开始实际清理，仍可正常登记资源并改用异步关闭。此 a8 后维护行为及实际测试见[资源登记与定义校验](../architecture/reviews/2026-10-29-resource-and-definition-admission.md)。

## 关闭、取消与错误

先完成或取消并 await 自己的驱动 Task，再 await runtime.aclose。框架等待托管同步线程，Engine.close 检查实际驱动/调用是否结束；不自动取消驱动。Engine 确认关闭后，逆序清理客户端。客户端 aclose 只清理资源，不能启动新的业务操作。

异步关闭开始后，或同步 Engine 已成功关闭后，新的公开入口和预先缓存的方法都拒绝使用；实际执行尚在途时执行权保留。正常实例因忙碌而在同步关闭前拒绝时，仍可通过原实例取消该 Run。同步 close/with 遇异步资源在关闭 Engine 前拒绝，提示使用 aclose/async with。

该保护覆盖 RuntimeInstance 的业务／观察端口，也包括 `send_input`、`patch_plan`、`compact_messages`、`parent_run_id`、`memory_stages`、`context_stages` 和 `context_artifacts`。即使调用方在关闭前缓存这些方法，或取消了外层 `aclose()` 等待，也不能在关闭中的实例上继续提交回复、修订计划或维护命令。需要继续任务时，先在原循环完成原实例的关闭，再用原数据库／Profile 建立新实例，读取原 Run 和回执。自定义 Engine 的额外端口需由扩展实现其生命周期契约。

取消外层 aclose 等待，实际清理 Task 仍被保留。随后 aclose 等待同一个 Task；失败资源保留，完成资源不重复关闭。取消之后晚到的清理失败在下一次等待报告，再次重试才发起新关闭。资源清理 Task 再次调用所属 Runtime/Context 清理会明确拒绝，避免等待自身；客户端及自建后台任务须遵循真实完成与幂等清理契约。

同步资源的 `close()` 回调也不能重入所属 Runtime／Context 的清理；同一 Context 正在清理时，第二个清理调用会被明确拒绝。资源回调只释放自己的资源，完整依赖树由外层持有者逆序关闭。重入错误未被组件处理时，当前资源保留，较早登记的资源尚不关闭；修正原因后对原实例重试。取消外层异步等待后，下一次清理继续等待已保留的资源 Task，不重新派发正在进行的 `aclose()`。这些 a8 后维护修复不在原 a8 两包中，实际回归及隔离安装范围见[关闭边界验收](../architecture/reviews/2026-10-29-runtime-cleanup-boundaries.md)。

owned 异步资源绑定创建循环；drive、排空与 aclose 使用同一循环，错误循环在调用 Engine 前拒绝。停止循环前完成清理；不隐藏 asyncio.run，不在线程里关闭 loop-bound 客户端。没有异步 owned 资源的同步实例保留原跨循环行为。

构造失败/取消会清理已登记资源。清理成功后传播原 RalfError/CancelledError；清理失败或再次取消时 RuntimeBuildError.cleanup 保留句柄，调用 await error.cleanup.aclose()。Store/Engine 工厂仍同步；被拒绝的部分 Engine 通过同步 close 检查并关闭执行权，不要求其提供合格的排空接口。正常实例仍严格检查排空完成，不能据此绕过实际线程存活检查。

a7 后维护源码在校验失败后先接管原候选，再读取关闭接口；关闭属性的读取错误也保留重试责任。此类被拒绝的 Builder cleanup 句柄从生成时就拒绝业务访问，只用于排空和关闭，不能被用来提交新 Run。原 a7 两包不含该修复；同步／异步反例和安装证据见[稳定性维护记录](../architecture/reviews/2026-10-25-runtime-failure-ownership.md)。

## 当前边界

配置可由 abuild 装配，但同步 ProfiledEngine 和 CLI --config/--factory 不支持异步工厂；build 选择已注册异步工厂时在创建数据库前拒绝。模板使用自己的 async Python 入口及原 Profile 选择；未交付通用 AsyncProfiledEngine。CLI inspect/status/events 仍可只读观察 SQLite。

dev13 提供可复用的生命周期。dev14 的[真实 Redis/PostgreSQL/Qdrant 适配器](remote-data.md)使用这一入口并通过原批次实际服务测试；后续分布式执行与Worker装配的所选支持范围见[Temporal配置](temporal-profiles.md)和[当前状态](implementation-status.md)。本指南的客户端生命周期不提供配置热监听、后台自动清理或强制终止外部调用。
