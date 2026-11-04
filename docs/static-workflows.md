# 静态图 Workflow

当前维护源码支持单 Coordinator 的静态串行／显式有界并行图：依赖、条件、输入映射、显式合并和持久恢复。串行 Agent／Transform 图使用计划 v1；含受管理 Tool 或异步 NodeExecutor 的串行图使用 v2，见[工具节点指南](managed-tools.md)与[异步节点指南](managed-async-nodes.md)。并行计划使用 v3，见[并行指南](parallel-workflows.md)。本页限定静态图。已交付的动态规划、团队及嵌套范围见[当前能力](implementation-status.md)；任意循环和流式数据流不由本页承诺。

## 1. 安装后直接运行

```sh
relf init my-graph --template graph
cd my-graph
python -m agent_app --input urgent --command-id urgent-task
python -m agent_app --input hello --command-id routine-task
```

编辑 `graph.json` 改 Agent、依赖、分支和结果映射；编辑 `runtime.toml` 改 Provider 与版本。模板使用离线回显，验证图执行和装配，不证明模型任务质量。输出包含所选分支的 `{echo, label}`，被跳过分支为显式 null。

```sh
python -m agent_app --input urgent --command-id queued-task --submit-only
relf --config runtime.toml resume RUN_ID
relf --config runtime.toml --format text inspect RUN_ID
```

替换 `RUN_ID` 为提交返回的 ID。`inspect` 显示计划和每个节点的状态；从其他目录运行时使用相同的绝对 `--db` 与 `--config` 路径。只读 SQLite 检查不会启动工厂或取得执行租约。

同一模板另有无需模型的 async Tool 应用 `python -m agent_app.tool_graph`，使用独立的 tool-runtime.toml、tool-graph.json 和恢复工厂，见[工具节点指南](managed-tools.md#安装后配置异步-tool-流程)。原 graph.json／runtime.toml 不需要修改。

## 2. Python 定义与默认组件

```python
import asyncio
from relf_agent import (
    AgentSpec,
    GraphNode,
    GraphWorkflowSpec,
    InputMap,
    Literal,
    RuntimeBuilder,
    RuntimeProfile,
    ValueRef,
)

flow = GraphWorkflowSpec(
    "report",
    [
        GraphNode("prepare", transform="identity"),
        GraphNode(
            "answer",
            agent=AgentSpec("answer", "Answer using the supplied input."),
            depends_on=("prepare",),
            input=InputMap({"task": ValueRef("prepare"), "language": Literal("中文")}),
        ),
    ],
    output=ValueRef("answer"),
)
profile = RuntimeProfile(
    "local-graph",
    "1",
    {"default": {"adapter": "offline-echo"}},
)
with RuntimeBuilder().build(profile, ".ralf/graph.sqlite") as engine:
    handle = engine.submit(flow, "prepare a report", command_id="report-001")
    print(asyncio.run(engine.drive(handle.run_id)))
    print(engine.diagnostics(handle.run_id).workflow)
```

节点声明顺序不要求拓扑顺序；默认解释器从满足依赖的节点中按声明顺序选择一个执行。Agent 节点走原有模型／工具循环，继承输出验收、审批、预算、效果核验、取消及独立响应／回执采纳协议。注册工具和真实模型的步骤见[工具扩展](extending.md)与[模型接入](model-adapters.md)。

## 3. 值引用、分支与合并

`ValueRef()` 引用原始输入；`ValueRef("read", ("items", 0))` 引用已完成节点的对象字段／数组元素。引用其他节点时，它必须是当前节点的依赖祖先。缺失、错误容器类型或被跳过的节点默认报错；`required=False, default=...` 显式选择回退。**null 是实际值，不能被缺失回退覆盖。** 字符串路径访问对象，非负整数路径访问数组；不支持任意表达式或 Python eval。

```python
from relf_agent import BranchCondition, GraphNode, InputMap, ValueRef

branches = [
    GraphNode("left", transform="identity", when=BranchCondition(ValueRef(), "left")),
    GraphNode("right", transform="identity", when=BranchCondition(ValueRef(), "left", negate=True)),
    GraphNode(
        "join",
        transform="identity",
        depends_on=("left", "right"),
        allow_skipped_dependencies=True,
        input=InputMap(
            {
                "left": ValueRef("left", required=False),
                "right": ValueRef("right", required=False),
            }
        ),
    ),
]
```

条件按规范 JSON 比较，`true` 与 `1` 不相等。条件为假时节点标为 skipped；默认依赖被跳过节点的后继也跳过。分支合并需要显式允许被跳过的依赖，并为其结果选择可选引用。没有 `output` 时，结果是已完成节点的 ID／结果映射；配置 `output` 时按绑定组成结果，可配 `output_schema` 验收，包括有意返回 null。模型自身的空输出仍遵循 Agent 的公共最终输出校验。

当前图遇到执行失败即整体失败；未执行节点保留 pending，已完成结果可诊断。取消停止后续调度，待执行／活跃节点标为 cancelled；已派发效果和晚到证据继续追踪。图默认串行；开启并行使用 max_concurrency，仍没有自动业务回滚。

## 4. 自定义组件

`WorkflowCompiler` 和 `WorkflowInterpreter` 都是纯同步端口，分别返回 `ExecutionPlan` 和 `WorkflowSelection`。默认 `StaticWorkflowCompiler` 将 Agent、顺序 Workflow 和图编译为上述 v1／v2／v3 计划；executor 声明纯转换为原 ToolNode。解释器可在已满足依赖的节点中改变选择顺序；引擎独立检查所选节点、输入、跳过集合和完成结果，禁止它绕过计划约束。

`NodeTransform` 是纯同步的 JSON 数据计算。默认 `IdentityTransform` 复制输入，只接受空配置。自定义示例：

```python
from relf_agent import GraphNode, GraphWorkflowSpec, LocalEngine, SQLiteStore, ToolRegistry


class SumValues:
    identity = {"kind": "sum-values", "version": "1"}

    def transform(self, input, config):
        return sum(input[config["field"]])


flow = GraphWorkflowSpec(
    "sum",
    [
        GraphNode(
            "total", transform="sum", config={"field": "values"}, output_schema={"type": "number"}
        )
    ],
)
engine = LocalEngine(
    SQLiteStore(".ralf/sum.sqlite"),
    providers={},
    tools=ToolRegistry(),
    workflow_transforms={"sum": SumValues()},
)
# Submit {"values": [1, 2, 3]} and drive; close the engine after owned work finishes.
```

配置工厂也可注册 `workflow_compiler`、`workflow_interpreter`、`workflow_transforms`；默认 adapter 分别为 `static`、`static`、`identity`，自定义映射由显式 `ComponentRegistry.register` 提供。异步节点使用 `workflow_executors` 组件，其默认 `identity` 工厂返回 NodeExecutorRegistry。参见[运行装配](runtime-assembly.md)。

变换不得调用数据库／网络、提交业务效果或启动线程；返回值必须已经是有限 JSON，awaitable、generator 和上下文管理器都不能代表完成。纯性是可信应用的契约，框架不会把任意 Python 代码变成安全隔离环境。需要外部 I/O 时使用受管理 Tool 或异步 NodeExecutor。

`GraphNode(executor="name", input=..., config=...)` 通过 `LocalEngine(workflow_executors=registry)` 选择已注册组件，调用 `async execute(input, config, context)`，传入完整 JSON、独立 config 和原 InvocationContext。NodeExecutorSpec 显式声明效果类别、版本、审批、成本与 Schema；Spec／节点输出 Schema 在原 Action 回执和结果保存后校验，失败保留已发生效果。NodeExecutorRegistry 借用组件，客户端关闭沿原应用或 BuildContext 的 owned／borrowed 契约管理。

内部保留 alias 对应的编译 ToolNode，包括 `from_plan` 往返，须与原计划、Manifest 和私有注册精确匹配；它不开放给 Agent.tools 或 tool_set binding。Local 串行、有界并行及 Team／Dynamic 嵌套图使用同一效果恢复路径；Temporal 当前拒绝 executor 图。完整注册、JSON／TOML 装配及[离线审批／重开示例](../examples/managed_async_nodes.py)见[异步节点指南](managed-async-nodes.md)。

## 5. 版本与恢复

首次接受命令时编译一次，保存不可变计划与节点输入／结果，固定编译器、解释器、使用到的变换／executor 注册和计划摘要。重提相同调用方请求返回原回执；恢复消费原计划，不重新编译。组件或后端变化会拒绝继续；新配置只影响新任务，旧版本及数据需要保留。

已保存模型响应、效果观察或节点结果按各自恢复边界继续。Agent 会话保存使用稳定消息 ID，即使保存后、节点完成提交前退出，也不会重复追加或重执行业务效果。纯变换在其原子结果提交前崩溃可重新计算，因此不能隐藏外部效果。下游效果保证仍依赖幂等键或核验接口。

默认旧 Agent／顺序 Workflow 保留已有记录和 Manifest。工作流扩展端口目前作用于 Graph 入口；旧入口使用兼容执行路径。需要主动使用新计划路径时：

```python
from relf_agent import GraphWorkflowSpec, StaticWorkflowCompiler

# sequence is an existing WorkflowSpec.
# graph = GraphWorkflowSpec.from_plan(StaticWorkflowCompiler().compile(sequence))
```

这是新声明／新 Run，不能把旧 Run 在执行中切换为图。Graph Manifest 含新的工作流协议身份，dev9 不支持继续这些 Run。IR 当前为 v1/v2/v3，限制 256 节点、引用路径 32 段、计划序列化 UTF-8 大小 1 MiB；节点结果、容量和清理仍有后续治理工作。真实故障与测试证据见[实现进展](implementation-progress.md)，完整 M1 门槛仍见[验收协议](m1-acceptance.md)。
