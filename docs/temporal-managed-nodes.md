# Temporal 受管理异步 Workflow 节点

2026-11-05 维护源码增加 `TemporalRuntime(workflow_executors=...)` 与 `GraphNode(executor=...)`。它复用 [Local 节点](managed-async-nodes.md)的 `NodeExecutorRegistry`、完整 JSON 输入、独立 config 和原 `InvocationContext`。源码和准确隔离 wheel 各13项真实 Temporal Service 恢复测试、各690项受影响离线回归已通过；原完整轮15479通过／1项旧夹具失败／908条件跳过，该夹具修复后源码／安装各8项通过，范围及证据见[本批验收](../architecture/reviews/2026-11-05-temporal-managed-nodes.md)。原 a8、推荐组合和此前节点验证包不包含本能力；准确制品和验收范围以[当前交付](current-delivery.md)为准。

## 支持范围

| 组合 | 当前源码范围 |
| --- | --- |
| 静态图 | 串行依赖与显式有界并行的 executor 节点 |
| 混合图 | 显式 Agent 节点与 executor 节点；Agent 仍需原 Provider |
| 嵌套 | 原 Team／Dynamic 中的上述图，沿原成员与子 Run 调度 |
| 数据 | 有限 JSON；注册的 input/config Schema 与两级结果 Schema |
| 配置 | SDK Registry 与 `TemporalProfile`／JSON／TOML 的 `workflow_executors` 工厂 |
| 效果 | 原审批、额度预留、未知效果核验、回执 ACK 与真实执行结束证据 |

首批限于无会话组合：不接入 Session／Turn、成员会话树、外置会话历史或跨 Turn 原生模型历史续接；不支持 Coding composition、部署准入及含 executor 图的 parent completion policy。跨 Turn 历史限制针对 `session_native_history` 等会话请求，不统一禁止混合图中 Agent 的原 per-Run 模型历史配置；executor 节点自身不调用模型。根或嵌套声明在子 Run 接受前检查这些限制。普通 Agent 的原有能力不因本批默认关闭。

普通 Tool／Transform 图节点、循环、reducer 和逐记录流式 Workflow 仍未扩展到 Temporal。模型／工具增量展示与这类数据流不是同一能力。输入、config 和输出的 Schema 保留 Temporal 原有的 `#` 引用子集；不要将 Local 支持的具名嵌入资源引用直接视为 Temporal 可用，见[Schema 指南](schema-validation.md)。

## 先运行无模型示例

[temporal_managed_nodes.py](../examples/temporal_managed_nodes.py) 使用原 `TemporalRuntimeBuilder`、默认 identity 节点与两个串行 GraphNode。它不调用模型或业务 API，但需要宿主事先安装包含本批实现的 SDK／Temporal 可选依赖，并明确提供 Temporal Service；脚本不会安装组件或启动服务。

```sh
python examples/temporal_managed_nodes.py \
  --address localhost:7233 \
  --task-queue relf-example-nodes \
  --command-id identity-001 \
  --input-json '[1, null, {"message": "完整 JSON"}]'
```

示例声明两个 cost=1 的只读 identity 节点，预算为2；成功时结果仍是完整输入，输出含 run_id、原提交回执和预算诊断。它不需要 Provider 或 EffectJournal。相同 command_id、定义、输入和预算找回原回执；新任务使用新 command_id，恢复时保留原 Profile、Scope、namespace、队列与注册代码。

示例的 `drive(..., wait_seconds=30)` 是一次进度等待；等待结束不等于取消业务 Run，也不改变工具、审批或业务期限。若仍未完成，应观察原 run_id 并按原发布继续驱动。不要改输入或换队列绕过原记录。

## 注册和装配

业务节点仍是普通结构化异步组件，无需继承框架类：

```python
from relf_agent import NodeExecutorRegistry, NodeExecutorSpec, TemporalRuntime, ToolRegistry

nodes = NodeExecutorRegistry()
nodes.register(
    NodeExecutorSpec(
        "lookup", "Read application data", effect="read_only", version="1", cost=1,
    ),
    my_async_component,  # async execute(input, config, context)，明确提供 identity
)
runtime = TemporalRuntime(providers={}, tools=ToolRegistry(), workflow_executors=nodes)
# 原 build_temporal_worker(..., runtime=runtime) 注册 Worker；图使用原 orchestration_release。
```

组件端口、identity、异步入口及借用客户端规则与[Local 节点指南](managed-async-nodes.md#sdk-注册与完整-json)相同。注册表借用组件；配置工厂通过原 `BuildContext.own/own_async` 明确登记 owned 客户端，Registry 不自行关闭客户端。普通 ToolExecutor 继续处理普通工具，私有节点使用固定注册适配器。

默认配置可放在原 Temporal Catalog 的 Profile 中；`kind="temporal-profiles"` 和 `schema_version=1` 沿用[既有装配契约](temporal-profiles.md)：

```toml
kind = "temporal-profiles"
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

JSON 使用同一结构。identity 工厂只接受空 config；自定义同步／异步工厂通过原 `ComponentRegistry.register/register_async` 返回 `NodeExecutorRegistry`，并使用 `TemporalRuntimeBuilder.abuild`。`providers={}` 仅在显式配置节点注册表时允许；混合图中每个 Agent 仍须解析有效 Provider。相同发布固定全部节点注册身份，不仅是某个图当前选中的注册。

业务写节点必须提供原耐久 EffectJournal；`requires_approval=True` 复用原 Action 审批，不能通过将写标为只读规避 Journal。宿主执行策略的 allowed_tools 同样约束内部节点 alias，注册本身不授予权限。

## History、预算和恢复

原 Parent History 负责依赖、并行额度、子 Run 身份和结果采纳。每个 executor 节点降低为原 Native Run Workflow 中的一项私有 ToolAction，不构造虚假 Agent／Provider，不调用模型，不在 Activity 内运行 LocalEngine，也不增加 Workflow／Activity 名称或第三套状态机。

节点发布显式带 `workflow_node_protocol=1`、全部 `workflow_nodes` 注册及对应私有 Tool Manifest。内部 `__relf_node__:<name>` 不进入公共 ToolRegistry 或 Agent 工具集合；只有原父发布、Scope、原 Parent Workflow epoch、子 Run、完整参数和已固定注册匹配时才派发。未启用节点的发布保留原协议路径；不能手工拼造私有子请求代替公共 GraphNode。

Parent 使用原子 Run 额度托管，按所选节点真实 cost 预留，支持 cost=0、1 或大于8；普通 Agent 子额度仍遵循原规则。节点只消耗原 Tool 额度，不收模型决策额度。预算不足在 execute 前拒绝，不创建独立预算账本；未知效果保持原额度与工作责任。

2026-11-09 已复现一项容量限制：默认节点 ToolExecutionOwner 为16槽，已被实际调用占用时，额外的未启动调用可能返回 `code=memory_backend_error`、`handler_not_started=true` 并使子 Run 失败。图的 max_concurrency 是调度上限，不保证单 Worker 或多个 Run 的执行槽可用；当前没有自动容量排队／恢复协议。显式增加 owner 上限只移动阈值，不能替代跨 Run 背压。不能根据进度缺失或一次拒绝自行重执行业务；这一限制列在[剩余能力](remaining-work.md)，本批节点扩展检查没有修改它。

执行沿原 dispatch intent、效果观察／回执、History 采纳与 ACK 推进。已确认结果还需真实 handler 停止、ACK（含延后 ACK）排空，节点才能完成。ACK 失败应修复原 Journal／Worker 路径后驱动原 Run，不能重新 execute。`queryable_write` 需要原 reconcile 证据；`unqueryable_write` 的未知效果保留人工核验，框架不能替代下游幂等性。

注册的 output_schema 与 GraphNode.output_schema 都验收；合法的 null、false、0、空字符串和数组不被 Agent 的非空回答规则拒绝。输出 Schema 不符时保留已确认的业务回执、效果与消耗，再使节点失败；不能用重新执行写操作修复结果。`EffectObservation(None)` 是确认 JSON null，reconcile 直接返回 None 则表示没有可采纳证据。

取消阻止后继调度，不能证明已发请求或 handler 结束。关闭仍沿原 Worker／Runtime／Assembly 排空与 owned/borrowed 顺序；取消关闭等待或收到 `CloseIncomplete` 后保留原实例和客户端，实际工作结束后重试 `aclose`。不要提前销毁 Journal 或业务客户端，也不要把终态快照当作所有关闭义务已经完成。

## 版本与待验收项

恢复必须保留原组件版本、Profile、namespace、队列和实际可处理原发布的 Worker。原节点未启用发布不增加节点字段；这不等于所有旧 History 都能用新 Worker 透明回放。尤其所选 Coding composition 固定 `_pure_sources` 实现指纹，本批共享纯规则变化会改变它；旧 Coding 任务须使用原包／匹配 Worker，不降低原指纹检查。

源码和准确隔离 wheel 已独立覆盖所选串并行／混合／嵌套、审批重启、未知效果、回执恢复及取消后真实停止与关闭重试，13项全部实际运行，无条件跳过。写提交后崩溃而缺少实际结束证明的用例，验收的是保留未知义务并阻止重写，并非业务成功。延后 ACK 的特定失败回路另有确定性状态测试；完整轮的唯一旧夹具缺项已定向修复，原模块源码／安装各8项通过；原15479通过／1失败／908跳过保留，没有再次全库运行。准确包为 `0.1.0a8+tnodes.3675891f64d0664f`，包内文档保留构建快照，最终支持范围和勘误以本页及验收记录为准。这些不授予真实模型质量、更多平台或公开发行资格。
