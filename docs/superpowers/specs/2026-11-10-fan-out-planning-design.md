# 有界动态批处理

基线 `aa77b90`。目标是让应用把有限输入列表分发给已有 Worker，再按输入顺序收集结果，或交给已有汇总成员。复用 `DynamicWorkflowSpec(plan_mode="dag")`、DAGProposal、ValueRef／InputMap 和 Local／Temporal 原父子权威，不增加 Workflow／Action 状态、执行后端或共享可变状态。

## 本批选择

统一模型参数增量需要显式新展示协议和兼容的语义流端口，持久 MCP Session 需要独立生命周期 owner，循环需要逐轮身份与恢复定义。这些单独后置。本批选择纯 `FanOutDAGPlanner`，将动态分发转成已有有限 DAG；不以普通汇总成员冒充任意共享 reducer／循环。

LangGraph 的 [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)提供动态分发和状态合并；[AgentScope 2.0 官方概览](https://github.com/agentscope-ai/agentscope/blob/main/README.md)提供团队和工作流能力。本批只缩小批处理接入差距，不进行跨框架质量或性能排名。

## 公共接口

`FanOutDAGPlanner(worker="worker", *, reducer=None, items_path=(), max_items=32, version="1")`：

- 是原 Planner 端口的不可变配置实现，`async plan(request, caller)` 只提出 DAG，不调用 caller、不做 I/O、不创建 Run。
- worker／reducer 是已有成员 alias，按原 identifier 规则校验；reducer 可以省略。items_path 使用原 ValueRef 路径规则，最长31段，为最后的列表索引保留一段；空路径表示输入本身是列表。
- max_items 为严格整数：无 reducer 时1..256，有 reducer 时1..255；version 为非空字符串。输入必须为非空 JSON 列表；缺路径、空／错误类型、过界、缺成员或超出原 constraints.remaining_steps／max_nodes 均明确 ValidationError，不截断或调用业务。
- 仅初始 revision=0 且 results 为空的规划请求；不自动重规划已接受工作。后续显式 pending patch 仍属于原宿主协议，不由此 planner 发起。
- 生成 `map-0000` 起的稳定节点，每个输入为原列表索引的 ValueRef，不复制业务数据到计划。没有依赖的 Worker 按原 max_concurrency 执行。
- 无 reducer 时，output 为稳定键 InputMap（map-0000等→已采纳子结果），不是完成顺序数组。有 reducer 时增加固定 id `reduce`，依赖全部 Worker，输入为同一结果映射，output 引用该成员的结果。
- 初始合法配置与运行中身份由原组件契约固定。更换配置／业务成员仍需新定义、Profile 版本和匹配宿主。

## 装配与兼容

SDK显式注入 `planners={"fan-out": FanOutDAGPlanner(...)}`；ComponentRegistry 提供 `planners/fan-out` 工厂，返回同名映射，供JSON／TOML的 Local／Temporal Profile 显式选择。SDK导出新增类。不得把它加入 Local 内置 planner 字典或 Temporal `default_components()`，后者的整表身份必须保持。

既有 Agent、静态图、Team、动态默认规划、DTO与绑定格式不改变。新增成员仍沿原权限、审批、子预算预留／结算、Session隔离、实际处理器停止和 unknown 核验。汇总只使用已完成的原子结果；失败、取消或未知效果不得被当作成功结果汇总。

## 验收与边界

覆盖配置和成员替换、逆序完成下稳定结果、并发／条数／原步骤限额、审批／预算／取消／unknown、提案保存／采纳／部分子结果保存的崩溃恢复，以及重复命令不重开子业务。使用真实 Local SQLite 和真实 Temporal Service／History 分层验证；未运行的服务不能记为通过。

提供一个无模型、可替换 Python Worker／汇总组件的完整示例，以及SDK与配置说明。冻结新私有候选，源码／准确安装同组回归、必要恢复、运行依赖与sdist比对、完整离线回归后本地提交。原制品／所有失败／并行网站文件保持，不推送或公开发布，不据此关闭完整R01–R26或宣称对等智能质量。
