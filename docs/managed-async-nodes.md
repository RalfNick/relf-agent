# 受管理异步 Workflow 节点

`GraphNode(executor=...)` 将完整 JSON 输入、独立 config 和原 `InvocationContext` 交给显式注册的异步组件。节点复用原 Action、审批、预算、效果核验和恢复日志，不需要模型，也不要求组件继承框架类。需要使用包含本能力的开发源码或验证安装包；原发行包的资格不能自动转用于本批能力；准确版本、安装验证及范围见[本批记录](../architecture/reviews/2026-11-04-managed-async-nodes.md)。

当前范围是 Local 单 Coordinator 的串行图、有界并行图，以及原 Team／Dynamic 中的嵌套图。Temporal 当前拒绝 executor 节点及 `workflow_executors` Local Profile 组件，包括嵌套定义。本页的离线 SQLite 示例不代表真实模型、业务服务或 Temporal Service 已验收。

## 运行同一份离线业务示例

[managed_async_nodes.py](../examples/managed_async_nodes.py) 模拟“审批后登记拣货回执”。输入是商品数组，config 独立指定示例仓库。业务客户端只写相邻的示例 SQLite 数据库，不读取密钥、不访问网络、不下载组件，也不修改实际库存。

在已经安装本批 SDK 的 Python 环境中运行：

```sh
python examples/managed_async_nodes.py --db /tmp/managed-node-demo/runs.sqlite --command-id receipt-001
python examples/managed_async_nodes.py --db /tmp/managed-node-demo/runs.sqlite --command-id receipt-001
```

也可以将同一个脚本复制到应用目录，保持文件名 `managed_async_nodes.py`，从任意目录以脚本绝对路径运行。脚本内部使用固定的应用模块入口，不能在恢复前重命名文件或改变代码版本。安装依赖由运行方事先完成，脚本不会自动安装。

首次运行在审批前关闭 Engine，然后重新打开同一执行库，批准原 Action 并完成业务；再次打开 Engine 重放提交和审批命令。输出包含原 submission／approval 回执、action_id、effect_key 和实际请求数。

| 字段 | 第一次运行 | 相同请求第二次运行 |
| --- | --- | --- |
| initial_state | waiting_approval | succeeded |
| requests_this_process | 1 | 0 |
| requests_total／effects_total | 1／1 | 1／1 |
| receipt_replay_matches | true | true |
| spent | 2 | 2 |

两次的 run_id、action_id 和 effect_key 相同。执行库保存框架权威记录；`runs.sqlite.business.sqlite` 保存独立的示例业务事实。业务表以原 effect_key 去重并检查相同键对应相同参数，这是示例的实际幂等保证，不能仅由框架声明推导。

希望在两个独立进程间观察审批等待，可使用另一组命令：

```sh
python examples/managed_async_nodes.py --db /tmp/managed-node-pause/runs.sqlite --command-id receipt-002 --pause-before-approval
python examples/managed_async_nodes.py --db /tmp/managed-node-pause/runs.sqlite --command-id receipt-002
```

第一条返回 waiting_approval，requests_total／effects_total 均为 0；第二条重开并完成原审批。相同 command_id 必须保持定义、输入、预算及会话参数相同。新的业务操作使用新 ID，不通过修改原请求重新执行。省略 `--db` 时使用临时目录，运行结束后删除示例数据库；跨进程演示需要显式保存同一个路径。

## SDK 注册与完整 JSON

示例的 `RecordReceipt` 是普通 Python 类，公开端口为：

```python
class RecordReceipt:
    @property
    def identity(self):
        return {"kind": "example-receipt-node", "version": "1", "ledger": str(self.client.path)}

    async def execute(self, input, config, context):
        # input 是整个商品数组，不展开成函数 kwargs。
        return self.client.record(input, config, context.effect_key)

    async def reconcile(self, input, config, context):
        receipt = self.client.receipt(context.effect_key)
        return None if receipt is None else EffectObservation(receipt, "offline-ledger")
```

完整代码还包含借用客户端的构造、一次异步让出和独立 Schema。注册及图声明使用公共 SDK：

```python
from relf_agent import GraphNode, GraphWorkflowSpec, NodeExecutorRegistry, NodeExecutorSpec, ValueRef

nodes = NodeExecutorRegistry()
nodes.register(
    NodeExecutorSpec(
        "receipt", "Record an offline example receipt",
        effect="idempotent_write", version="1", requires_approval=True, cost=2,
    ),
    RecordReceipt(client),
)
flow = GraphWorkflowSpec(
    "receipts",
    [GraphNode("record", executor="receipt", config={"warehouse": "offline-demo"})],
    output=ValueRef("record"),
)
# LocalEngine(store, providers={}, tools=ToolRegistry(), workflow_executors=nodes)
```

执行完整业务请使用脚本的 `make_registry(client)` 和 `workflow()`，保留其完整 config／Schema，而不是将上面的节选覆盖到已有 Run。输入可以是对象、数组、字符串、数值、布尔或 null；只有满足该注册的 input_schema 时才派发。config 始终是独立对象，可用 config_schema 限制。input_schema 默认 True，config_schema 默认 object，output_schema 默认 None；effect 必须显式填写。

注册要求非空 JSON identity 和真正的 async execute；可选 reconcile 也必须是真正异步方法。async callable 对象同样支持。同步函数返回 coroutine、generator 或上下文管理器不能充当此端口。直接方法、代码入口和声明身份在派发及结果接收边界复核；组件内部客户端、闭包和外部依赖仍需要集成方通过版本／identity 固定，不能把这些检查理解为任意 Python 沙箱。

## 默认 identity 的 JSON／TOML 装配

默认 adapter 只复制完整输入，不访问业务服务；该装配工厂只接受空 config。以下两个文件等价，选择一个保存。

`node-runtime.json`：

```json
{
  "schema_version": 1,
  "default": {"name": "nodes", "version": "1"},
  "profiles": [{
    "name": "nodes",
    "version": "1",
    "providers": {},
    "components": {"workflow_executors": {"adapter": "identity", "config": {}}}
  }]
}
```

`node-runtime.toml`：

```toml
schema_version = 1
[default]
name = "nodes"
version = "1"

[[profiles]]
name = "nodes"
version = "1"
providers = {}

[profiles.components.workflow_executors]
adapter = "identity"
[profiles.components.workflow_executors.config]
```

使用原装配入口运行，不需要 Provider：

```python
import asyncio
from relf_agent import GraphNode, GraphWorkflowSpec, RuntimeBuilder, ValueRef, load_catalog

profile = load_catalog("node-runtime.toml").default
flow = GraphWorkflowSpec(
    "copy", [GraphNode("copy", executor="identity")], output=ValueRef("copy")
)
with RuntimeBuilder().build(profile, "identity-runs.sqlite") as runtime:
    handle = runtime.submit(flow, [1, None, "完整输入"], command_id="copy-001")
    print(asyncio.run(runtime.drive(handle.run_id)).result)
```

实际混合 Agent 图仍需为 Agent 注册有效 Provider。identity Profile 和业务示例使用各自的数据库／定义，不能替换已接受任务的原 Profile。

## 通过原组件工厂替换

业务示例直接借用客户端，并在所有驱动与 Engine 结束后自行关闭。需要 Profile 管理生命周期时，在复制了示例脚本的应用目录显式注册工厂：

```python
from managed_async_nodes import ReceiptLedger, make_registry
from relf_agent import ComponentRegistry, RuntimeBuilder, RuntimeProfile
from relf_agent.errors import ValidationError

def validate_ledger(config):
    if set(config) != {"path"} or not isinstance(config["path"], str) or not config["path"].strip():
        raise ValidationError("Declare one local example ledger path")

def build_nodes(config, context):
    client = context.own(ReceiptLedger(context.path(config["path"])))
    return make_registry(client)

components = ComponentRegistry()
components.register("workflow_executors", "receipt-ledger", build_nodes, validator=validate_ledger)
profile = RuntimeProfile(
    "receipts", "1", {},
    {"workflow_executors": {"adapter": "receipt-ledger", "config": {"path": "business.sqlite"}}},
)
# with RuntimeBuilder(components, base_dir=app_directory).build(profile, run_db) as runtime:
#     使用同一脚本的 workflow()、ITEMS 及原审批流程。
```

validator 保持纯同步，不连接数据库；工厂创建客户端时立即登记到原 BuildContext。`own` 要求同步 close，`own_async` 要求异步 aclose。需要异步创建或关闭客户端时使用 `register_async`、`await RuntimeBuilder(...).abuild(...)` 和 `async with`／`await runtime.aclose()`；仍使用原资源台账，见[异步装配](async-assembly.md)。

NodeExecutorRegistry 始终借用组件，不自动调用 close/aclose。工厂以外创建的共享客户端由应用关闭；不要让两个 Runtime 同时拥有同一个客户端。退出前完成或取消并 await 自己的 drive Task，再排空实际工作、关闭 Engine／Runtime，最后关闭借用客户端。取消等待不证明真实执行或远端请求已结束。

## 原 Action、Schema 与效果恢复

纯编译器把 executor 声明转换成原 ToolNode：串行计划为 v2，有界并行为 v3。内部参数是 `{"input": 完整输入, "config": 节点配置}`，不是另一套调度协议。InputMap 支持有限递归，最多 32 层 map；编译包装自身占一层，因此 executor 原输入映射最多使用 31 层。普通图的引用、分支和并行限制继续适用。

内部 `__relf_node__:<name>` 是保留 alias，不属于 Agent.tools，也不能通过 tool_set binding 获得。编译后的 ToolNode（含 `from_plan` 往返）只有在原计划、Manifest 和私有注册都精确匹配时才能派发。模型看不到这些私有工具；自定义普通 ToolExecutor 仍处理普通工具，节点由固定私有适配器执行。适配器的 Registry 归属、直接方法与代码入口同样固定，变更后须恢复原实现再继续。策略和审批看到固定 ToolSpec 及完整包装参数。

调用沿原 `dispatch intent → effect_observation／receipt_received → ResultCommit → 节点完成` 推进。已有观察恢复不重新 execute／reconcile；Action 已完成而节点未完成时只继续结果验收。Spec.output_schema 和 GraphNode.output_schema 都在原回执、结果及预算事实保存后验收；失败保留已发生效果，不能重新执行业务写入来修复输出。非有限 JSON 无法形成可保存观察，仍需保留未知窗口。

| effect | 未知结果时的行为 |
| --- | --- |
| read_only | 优先恢复已有结果；无结果时按原权限与预算条件建立新读取 Attempt |
| idempotent_write | 优先核验；仅依赖下游实际保证的相同 effect_key／参数去重继续 |
| queryable_write | 必须注册 reconcile；无权威证据时停泊，不因暂时查不到而重写 |
| unqueryable_write | 无证据时等待人工核验，不自动补发未知写 |

`reconcile(input, config, context)` 返回 `EffectObservation` 或 None。`EffectObservation(None)` 表示已确认结果为 JSON null；直接 None 表示没有可采纳证据。人工确认继续使用 `engine.reconcile(..., command_id=...)` 的原命令去重。核验不拥有 Run 状态，也不负责业务重试。

取消阻止后继调度，已经发出的效果仍可能发生。晚到观察可以保留为效果证据；终态、已有 ResultCommit、实际运行归属和未知预算不会因取消而清零。原版本、组件身份、数据路径或 config 变化时，应建立新发布并保留旧实现恢复，而不是绕过 DefinitionMismatch。

Local 串行、显式有界并行及嵌套图复用上述边界；本批没有增加循环、reducer、逐记录流式 Workflow 或跨 Worker 接管。真实外部服务的幂等期限、核验一致性、取消和资源隔离需要独立验证。
