# 通用受管理异步 Workflow 节点

## 用户目标与范围

用户明确要求在既有架构、执行权威和恢复契约下补齐通用受管理异步节点，并完成回归、隔离安装、能力文档和本地提交；单次跳过钩子，不推送或公开发布。本设计落实既有 framework-capabilities 的 NodeExecutor 目标及 R08，不重新定义整体框架。

基线 `e75c756`。首期为 Local 静态图的串行、有界并行，以及原 Team／Dynamic 中嵌套图。模型、Tool、纯 Transform 节点保持原行为；Temporal 继续拒绝非 Agent 图及本批 Local 组件。不是引入任意代码配置、循环、reducer、流式数据流或另一套调度器。

## 方案取舍

采用公开 `GraphNode.executor` 声明、版本化 `NodeExecutorRegistry` 和结构化 `NodeExecutor` 端口，由纯编译器 lower 成原 v2／v3 Tool 节点。原 Action 日志、审批、预算、未知效果、响应接收及 ResultCommit 继续唯一推进状态。

不新增 `action.kind=node` 或 v4 调度计划：原 IR 的受管理 ToolAction 已能准确表达该行为；新 action／版本会要求改写大量恢复与并行判断而不增加本批语义。也不允许 async Transform 隐藏 I/O。

原公开 ToolRegistry 与 NodeExecutorRegistry 私有执行注册表分开，不把 node executor 暴露给模型。普通自定义 ToolExecutor 继续接收普通工具；节点使用固定的私有适配器，不能假定用户执行器认识内部名称。

## 公共端口与默认实现

```python
class NodeExecutor(Protocol):
    identity: dict
    async def execute(self, input, config, context): ...

# 可选结构化端口；queryable_write 必须提供。
class NodeReconciler(Protocol):
    async def reconcile(self, input, config, context): ...

nodes.register(
    NodeExecutorSpec("enrich", "Enrich input", effect="read_only", version="1"),
    executor,
)
GraphNode("enrich", executor="enrich", config={"mode": "full"})
LocalEngine(..., workflow_executors=nodes)
```

`NodeExecutorSpec` 冻结 name／description／显式 effect、version、requires_approval、cost、input_schema、config_schema、output_schema。name 使用 `[A-Za-z][A-Za-z0-9_.-]{0,63}`。effect 没有隐式默认；沿原四类效果及预算规则。input_schema 默认 True，config_schema 默认 object，output_schema 默认 None；Schema 可以是合法对象或布尔值。

execute 接收整个有限 JSON（包含数组、标量和 null）、独立 config 对象，以及原 InvocationContext，不展开成 Python keyword arguments。execute 返回有限 JSON。reconcile 返回 `EffectObservation` 或 None；`EffectObservation(None)` 表示已确认 null，直接 None 表示未知。核验不负责修改 Run 或重试操作。

不要求第三方继承内置类；注册时校验 identity 和原生异步方法形状，拒绝同步返回 coroutine、generator 或上下文管理器的伪异步配置。默认 `IdentityNodeExecutor` 为可运行的异步复制实现，用于离线装配与替换验证，不宣称业务智能或外部 I/O 质量。

Registry 借用 executor，不隐式关闭其客户端。配置工厂可通过原 BuildContext.own／own_async 管理客户端；仍由原 RuntimeInstance 排空／关闭和失败重试。不会新增后台任务或资源台账。

## 声明、编译与旧身份

GraphNode 的 agent／transform／tool／executor 四选一，config 仅 transform／executor 可非空；executor 字段只在实际选用时序列化，旧节点不增加 executor:null。

公共图保存原 executor 声明。共享纯 lowering 将它变成 alias ToolNode，input 包装为 `InputMap({"input": original_binding, "config": Literal(config)})`，清空 plan node.config。为容纳已有 InputMap 输入，InputMap 递归接收 InputMap；绑定编码／解码有明确有限深度（32），不支持循环对象或无限树。

内部 alias 为 `__relf_node__:<name>`。lowered plan 仍为既有串行 v2／并行 v3；ExecutionPlan 拒绝未编译的 executor 字段。`compile(from_plan(plan))` 必须幂等。并行 frame 已收到包装后的 input，沿原 Tool v2 frame，不重复包装。

未使用 executor 时，旧 Graph／plan／Manifest／Profile canonical 字节保持。只有实际使用的注册进入 `workflow.node_executors`（protocol=1、固定私有 ToolExecutor identity、selected registrations），内部 Tool Manifest 进入原 tools 字段。增加未使用的注册不改变已有 Run 的 Release。新定义在旧 GraphNode 解析时拒绝；旧执行实现不能重建新节点 Manifest，禁止继续新 Run。

## 身份、授权与派发

Registry 保存固定 executor 对象、identity、execute／reconcile 直接方法及代码入口。持久身份包括显式 NodeExecutorSpec、组件 JSON identity、直接入口摘要及内部适配协议；运行时在派发前、await 后与结果序列化后复核对象／代码。实例状态、闭包、默认值和外部依赖由集成方显式版本／identity 负责，不递归证明任意 Python 执行图。

NodeRegistry 提供内部 ToolRegistry 与固定 ToolExecutor 适配器。内部名称不进入公开 tools.descriptions、AgentSpec.tools 或 binding tool_set。禁止公开工具与该保留命名空间碰撞。私有路由必须同时校验原 plan 对应 node 为非 Agent、精确 tool alias、该节点选定 Manifest 和私有注册记录，不能只判断前缀。

授权策略和审批看到原 ToolSpec（名称是 alias，config 含 executor 注册身份）及完整 `{input, config}`。原操作 digest 包含固定 Manifest 和包装参数；config、输入或实现变化必须形成新发布。原 Action ID／effect_key／budget reservation 不重置。

仅有结构化端口不代表安全沙箱。可信 async executor 自己管理网络超时、幂等服务和核验接口；不能启动未受管理的后台写任务后直接返回。

## 恢复、结果与取消

完全复用 kind=tool 的 dispatch intent → effect_observation／receipt_received → ResultCommit → workflow_node_completed。已保存响应恢复不再 execute／reconcile；Action 已完成、节点尚未完成时只完成节点。

原四类未知效果保持：read_only／idempotent_write 可以按原条件重试；queryable_write／unqueryable_write 无证据时等待核验，不盲重发。人工 reconcile 使用原命令与去重。有限 JSON 才能保存观察；NodeExecutorSpec.output_schema 和节点 output_schema 在原 Action 结果保存后、节点完成前检查，失败保留已发生效果／回执／预算，不重跑业务以修复输出。

取消观察、取消业务与 executor 实际退出继续区分；节点不创建新的驱动 Task。原 drive／Runtime 托管及 shield 保留归属，吞掉取消而继续执行的 handler 未结束前不能关闭／释放 Coordinator，不调度后继。外部效果不因取消而回滚。

## 装配与支持矩阵

LocalEngine 可选 workflow_executors 参数；RuntimeProfile 增加同名可选组件。内置 `workflow_executors/identity` 只接受空 config，构造包含 identity 注册的默认 Registry。第三方通过原 ComponentRegistry.register／register_async 返回自定义 Registry；SDK／JSON／TOML 不导入任意模块，工厂预检和原 owned／borrowed 生命周期保持。

TemporalProfile 将 workflow_executors 列为 Local 组件；Temporal 请求、嵌套请求与 Worker 权威继续拒绝新 executor 声明，错误发生在 RPC／Activity 前。没有完成真正 History 故障窗口验收前不宣称分布式支持。

## 验收

1. 第三方不继承的 executor、默认实现、完整 JSON／config、嵌套 InputMap、混合 Agent／Transform／Tool 图、有界并行／分支／嵌套流程。
2. 授权拒绝、审批前零执行、预算不足、重复控制请求、方法／identity 漂移、输出 Schema 失败保留原效果、私有名称隔离、自定义普通 ToolExecutor 不截获节点。
3. 真实子进程崩溃窗口：intent 后／外部完成观察前／receipt_received 后／Action 完成节点提交前；断言效果、稳定键、执行／核验次数及预算。
4. async handler 取消后继续执行、并行失败、驱动观察取消、关闭失败重试，不新增 lease／调度权威。
5. 旧 v1／v2／v3 原字节、旧安装包双向默认恢复、Temporal 全部拒绝入口；相关源码与 checkout 外准确安装同一测试选择。
6. 构建独立私有验证 wheel／sdist，最小依赖首用、产品逐文件核对、原290+制品与用户未跟踪review保持。文档分别标实现／本地验收／未验收，不借旧平台／模型成绩授予本批资格。
