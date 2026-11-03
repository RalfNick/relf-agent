# 基础工具与增量配置补齐

## 目标与依据

2026-11-03 用户要求持续优化并补充缺失能力。本批从既有 R04／R12／R22 中选择两个独立的小范围缺口：固定 HTTP GET 查询、现有增量展示策略的 Profile 声明。用户此前已要求按清单持续执行和并行推进，本批沿该方式实施，不重新开启整套架构设计。发布、推送与官网部署仍不在授权范围。

源码基线 `f0bf274`。已有 Agent／图／Plan／Team、自动上下文、RAG、记忆及增量流不重复开发。保留 Local Coordinator／Store 和 Temporal History 各自唯一执行权威；不新增执行状态机、后端、依赖或公开 Alpha，不改写历史制品与验收。

## 方案选择

- **采用：扩展原 ToolSource 与组件注册机制。** GET 复用原 HTTP 客户端及实际线程归属；增量策略复用现有 Engine／Activity 参数和 Manifest。改动小，默认行为和恢复身份可保持。
- 通用 HTTP 请求模板或自动 Provider 流式转换会引入更多输入、凭据和资源所有权规则，本批不采用。
- StreamChannel、任意异步节点、循环／quorum、完整异步 Profile Router 和新适配契约套件分别有独立恢复责任，本批不混入。

## 固定 GET 查询

`HTTPToolSource(..., method="POST", query_parameters=None)` 默认维持原 POST。仅支持精确大写 POST／GET；POST 不能设置 query_parameters。URL、方法、头和映射由宿主固定，不接受模型动态改变，不跟随重定向或自动重试。

GET 将 arguments 的键按名称排序后编码为查询参数；默认参数名等于 argument 名。显式 `query_parameters` 为 argument 名到目标参数名的一一映射；实际 argument 必须有映射，缺省的可选 argument 不发送。名称须非空且无空白／控制字符，目标参数名不能重复。输入支持字符串、有限数字、布尔值，以及这些标量的非空列表（编码成重复键）；布尔编码 true／false。null、对象、嵌套列表、空列表和不完整映射在派发前拒绝，避免静默丢参。

GET 不发送 JSON body／Content-Type，固定 Accept-Encoding 为 identity。原 canonical JSON 输入和实际 UTF-8 URL 编码查询分别受 max_input_bytes 限制；响应继续使用原 Schema、有限 JSON、输出限额与脱敏错误。查询参数应避免秘密，实际 URL 日志由业务服务治理。

原 POST identity 与请求编码逐字段保持；仅 GET identity 增加固定 query_parameters。GET 不自动决定业务效果或取消审批：宿主 ToolPolicy 仍是权威。原 Action、预算、审批、稳定效果键、received observation 和真实处理器关闭沿用原实现。

JSON／TOML `tools/http-json` 接受相同 method／query_parameters；在分配数据库／客户端前纯校验，owned Source 继续由原装配台账管理。

## 增量策略声明

RuntimeProfile 与 TemporalRuntimeProfile 接受 `components.stream_updates = {adapter: "bounded", config: {...}}`。config 只允许 StreamUpdatePolicy 已有的 max_deltas、max_bytes、max_payload_bytes、publish_timeout 四项，默认值及限额保持原规则。同步／异步 Local 与异步 Temporal Builder 通过原组件注册机制装配，不再设置另一份策略。

省略组件仍为 None，原 Manifest 不新增字段；选择后固定既有 policy.identity。未知字段、错误类型和超限值必须在资源分配前拒绝。改变配置应使用新 Profile version，不能继续原 Release；原 Profile／原配置重开后复用 Run 与事件。

该组件启用展示接收，不自动把 Provider.complete 改为 stream。异步工具仍须显式 emit_tool_delta；模型须原 StreamedModelProvider／宿主已注册 Provider 工厂，原 wrapper 清理债务由持有者负责。本批不新增 wrapper 工厂，不借配置组件接管客户端或流迭代器。

观察取消只结束观察，业务取消仍走原命令。Temporal 声明仅证明装配和原 Activity／History Manifest 一致，不借离线测试宣称新的真实 Service 故障窗口已验收。

## 验收与交付

- 先以失败测试证明两项缺口，再实现最小变化。HTTP 用本机真实服务验证实际方法、编码、零 body、限额、无重试／跳转、取消后排空和 Profile 重开审批／去重。
- Local 同步／异步、JSON／TOML 配置工具增量；缺省原 Manifest、非法配置零分配、原 Run／事件恢复和观察取消。Temporal 使用现有离线 SDK 装配／Manifest 测试，真实服务资格单列。
- 运行受影响及相邻测试、Ruff／格式／空白检查，构建独立本地验证包并在 checkout 外安装运行同一选择。冻结原包哈希清单，确认旧制品未改；没有外部模型调用或账号操作。
- 同步能力清单、开发队列、专题文档与验收记录，分别注明已实现／离线验收／未验收。当前推荐冻结候选继续保留，新代码与本地验证包另列，不把历史平台资格授予本批。
