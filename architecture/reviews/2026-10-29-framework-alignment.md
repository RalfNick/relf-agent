# 框架能力 review 与对齐增量

日期：2026-10-29。代码基线 `2f1b5b5`；本批工作区增量与原 a8 制品分开。检查能力清单 R01–R26、公共入口、模型／工具／编排、数据与观察实现、恢复契约及历史证据。本轮是架构／实现审查和所选受影响回归，不是全 SDK、真实模型、全部后端或安全审计的重新验收。

## 结论与比较口径

Relf 已是具备较丰富能力、重视审批与业务效果恢复的通用 Agent 框架预览。基础文本 Agent、常见图／Plan／Team、Session、上下文、记忆和 RAG 已成体系；默认智能质量、进阶扩展便利性、交互与集成生态、完整生产治理仍有差距。不能认定整体达到或超过 AgentScope／LangChain＋LangGraph，也没有对等 benchmark 证明质量、性能或可靠性更优。

比较三种不同职责：

- [AgentScope 当前 Agent 文档](https://docs.agentscope.io/en/versions/2.0.12dev/building-blocks/agent/overview)是开发版本资料，描述统一循环、上下文、中间件、权限与事件入口，以及 reply／reply_stream。它不等同于稳定发行的全部生产资格。另参考用户指定的本地 AgentScope `2.0.10dev`／`48c4b9ce`（2026-10-08）源码，不能将该旧快照当上游最新稳定版。
- [LangChain](https://docs.langchain.com/oss/python/langchain/overview)提供可组合 Agent 与模型／工具／中间件入口；[中间件](https://docs.langchain.com/oss/python/langchain/middleware/overview)能变换输入、控制调用与组合多种行为。不能把它只理解为早期链式调用库。
- [LangGraph 图 API](https://docs.langchain.com/oss/python/langgraph/graph-api)提供通用状态、函数节点、循环、路由与 reducer；[持久化](https://docs.langchain.com/oss/python/langgraph/persistence)提供检查点／恢复等基础。外部副作用仍需要应用处理幂等和恢复，不能仅凭检查点或 Relf 的 Action 协议判断谁更可靠。

[LangChain 流式接口](https://docs.langchain.com/oss/python/langchain/streaming)覆盖 Agent 进度、模型 token、自定义更新等。Relf 的持久 Run 事件和 Provider SSE 是其中不同层次的子集。LangSmith 托管、独立服务与商业平台不作为开源 SDK 已交付能力直接相加；AgentScope 应用／Runtime 组件也按其部署层区分。

## 能力完整性：对照 R01–R26

“已有”表示能找到实现和对应指南，完整资格仍以该组合的验收为准；不按接口数打分。

| 能力／清单 | Relf 当前基础 | 主要缺失／不足与对齐方向 |
| --- | --- | --- |
| Agent 与能力绑定 R01–R03/R07 | AgentSpec／AgentHarness／AgentRun、逐成员能力与限制、统一控制和原发布恢复 | 高级受管理阶段与 selector 仍有内置实现耦合；更多能力包及真实独立替换体验未验收 |
| 配置 R04 | JSON／TOML、注册工厂、固定版本、同步／异步资源装配 | Temporal 推荐组合与异步 CLI 路由不足，缺完整迁移／弃用策略；不能用热换配置继续原 Run |
| 模型 R05 | Chat、Responses、Anthropic、Gemini、DeepSeek 文本／函数及部分推理续接 | 真实国内外／本地型号矩阵、统一错误／用量、路由与 fallback；协议实现不等于每个模型可用 |
| 多模态／实时 R06 | 当前核心消息和 Provider 以文本为主 | 图片／音频／视频及内容来源／限额、实时语音／TTS 未交付；不以兼容 URL 冒充支持 |
| Workflow R08/R09 | 顺序、图、分支／映射、并行、Agent／Tool／Transform 与嵌套 | 相比通用 StateGraph，缺受管理异步自定义节点、类型化共享状态／reducer、循环和 quorum 等组合；逐记录带背压的数据流未实现 |
| 动态规划／多 Agent R10/R11 | 计划／修订／DAG、Plan／Router／Supervisor、子 Run、预算／取消传播、澄清输入 | 类型化交接、受控共享状态、复杂重规划和跨权威协作；固定规则／Supervisor 的参考成绩不是任意自主团队质量 |
| 工具与环境 R12/R13 | typed Python、MCP stdio／有限 HTTP、HTTP／CLI、Workspace／Skills、所选 Docker／Coding Runner | 单 Agent 同轮工具仍逐个执行，图并行不能替代工具批次并发；常用业务工具包少，MCP 持续会话／OAuth、文件操作／权限、远端沙箱与完整隔离治理仍不足 |
| 上下文 R14 | 有界历史、完整工具组、摘要、产物卸载、规则／模型阶段、tokenizer | 完整模型协议计量和长上下文保真质量不足；默认字节／散列基线不能替代真实模型能力 |
| 短期／长期记忆 R15 | Session 与 Facts 分离，memory／SQLite／Redis／PostgreSQL、CAS／TTL／来源、自动提炼与语义召回 | 语义冲突／撤回／遗忘、多事实原子采纳、增量索引与大历史效率、跨时间真实利用评测仍未闭环 |
| 摄取与 RAG R16/R17 | 解析／分块／Embedding／混合召回／融合／重排／来源回读；有限参考任务证据 | 业务连接器、OCR／复杂布局、语义分块、索引修复／删除传播和 pgvector 等按需适配；现成集成生态明显较窄 |
| Artifact／缓存 R18 | memory／SQLite／POSIX JSON 产物、namespace／TTL／容量及受管理卸载 | S3／binary、引用保留／孤儿清理、全局磁盘治理和缓存协议未完成 |
| 执行／通信 R19/R20 | 单 Coordinator Local；独立 Temporal History；所选高级组合、Inbox／Outbox、Redis Streams／PG 交接、A2A polling | Local 多进程 Worker、长期 History 管理、更多后端一致性／升级故障门禁、A2A SSE／push 等仍不足；数据适配器不是分布式执行权威 |
| 控制与治理 R21/R24 | 原命令／审批／核验／未知效果、执行 credits、有限容量／期限／身份／审计／保留和备份 | 完整企业 OIDC／ACL、真实费用、跨宿主资源容量、HA／生产恢复与运维平台未交付 |
| 事件／服务 R22/R23 | 持久事件游标、观察式中间件、有限 HTTP 控制；本批补统一高层订阅 | 模型 delta／工具增量尚未统一，OTel／metrics、完整服务资源库／UI／渠道／后台任务不足。事件订阅不等于流式节点计算 |
| 扩展／质量／开源交付 R25/R26 | 明确端口及装配、部分 conformance、starter／教程／安装／恢复、有限真实参考链路 | 仍需外部开发者采用、同模型／工具／任务的对等比较、更多线上型号及平台验收；PyPI 与原 a8 公开交付不由维护测试放行 |

更细边界保留在[完整能力清单](../../docs/remaining-work.md)，本轮不把已有 Redis／PG／向量数据库、自动上下文或 Temporal 高级编排误列为“完全未开发”，也不把有限实现标成整体完成。

## 架构、扩展性与易用性

继续保留：策略提案与执行权威分离；每 Agent 绑定与宿主授权分离；Session／Facts／Knowledge／Vector／Artifact 与执行事实分离；模型响应／效果回执先接收、再采纳；Local／Temporal 各自唯一权威。它们直接服务审批、未知效果与恢复，值得保留。

主要维护风险是集中度和组合成本：[LocalEngine](../../src/relf_agent/engine.py)约 2,871 行，[Temporal 主 Workflow](../../src/relf_agent/temporal_workflow.py)约 2,109 行，另有大量按阶段拆出的模块。复杂度不靠再增加 Facade 或 RuntimeKernel 名称解决。应以具体用例提取共用纯规则、减少重复校验，保留后端自己的状态推进；不能为模仿通用 hook，让 hook 吞掉真实效果回执或取得调度权。

默认首用已有离线 starter 和[连续工单路径](../../docs/support-journey.md)，进阶使用仍需理解效果类别、版本固定、资源所有权和多类数据端口。优先降低组合成本，明确结构化端口、继承扩展和暂不支持的区别；避免为了简短示例将任意 Python 函数隐式认定只读，或给未知外部效果自动重试。

## 本批实际开发与修复

1. **H2/R22 高层观察入口：** `AgentRun.subscribe_events()` 直接返回原 `RunEventSubscription`；Local／Temporal 均固定原 RunRef，实际读取继续经过原 Scope／Release 校验。支持原游标、分页、只读快照／持续跟随、读取期限和条数限额，不暴露或接管底层 Engine。原 `events()` 分页 API 保持。
2. **P2 事件返回值错误边界：** 事件页／Envelope／状态在深拷贝前共用有限 dataclass JSON 序列化；原生对象／嵌套协程／循环数据和非字符串状态统一为 ValidationError，拒绝整页时不推进游标。合法嵌套 DTO 序列化保持；无效原生对象由生产方清理。
3. **生命周期与恢复：** 断连／取消只停观察，不隐式 drive、resume 或取消业务；订阅不关闭 Runtime／Worker；Runtime 关闭后连缓冲记录也拒绝。实际 SQLite 审批重启、游标重连、重复批准与一次效果恢复纳入回归。Temporal 当前仅模拟传输＋实际状态类证据，不代签真实 Service。
4. **文档：** 入口示例、版本边界、当前对齐状态与历史冻结队列分开；不将新增便利方法当完整 token stream、R09 或整体框架对齐。

此增量沿已批准的 [H2 契约](../specs/agent-facade-session-contract.md)：事件代理且关闭订阅不取消业务。无新执行权威、Schema、依赖或默认付费调用，原包不重建。

## 验证与证据

证据位于 `dist/alignment-20261029/`，原失败保留。初轮新增入口 11 failed／1 error：入口缺失；同时新测试在方法缺失时未及时释放阻塞 Provider，另一个手工 Runtime 夹具漏关闭，导致 30 秒收尾和资源警告。修正测试清理并保持产品未改后，入口与事件边界反例 **27 failed／零错误**。最小实现后相关六模块 **168 passed**，`-W error`。

首轮扩大源码 **840 passed**、隔离安装 **767 passed**；审查又复现本批新入口的 P2：Runtime 已排空且 owned 资源关闭失败后，普通 handle 查询已拒绝，订阅仍能发缓冲事件。追加反例 **1 failed／10 deselected** 后，读取前增加 `_drained` 检查，不追加权威 I/O；修复后相关六模块 **169 passed**，并验证保留原游标和安全重试关闭。首轮日志、输入及私有 wheel 均保留，不拼接为最终全绿。

| 最终验收 | 结果 |
| --- | --- |
| 源码 58 模块 | **841 passed**，85.44 秒，`-W error`，零失败／错误／跳过；47 个核心与 11 个 Temporal 离线模块 |
| 源码目录外安装 47 模块 | **768 passed**，70.54 秒，`-W error`，零失败／错误／跳过；与源码对应核心完整 `(classname, name)` 一致 |
| 最终私有制品 | `0.1.0a8+maintenance.e6031090ed15c3cf`；SHA-256 `a2f634129f30dca18edca0826aa4e6c3a3bb97bfc50a37131104e757887387f6`；独立 venv／site-packages 导入、METADATA／模块版本、pip check、LICENSE／NOTICE 和 443 个产品文件核对通过 |
| 安装设置 | 测试文件／断言原样复制；检查目录没有 src。仅异步 starter 的 installed_wheel 夹具沿用安装运行器，使用这份精确私有包的 Python／CLI，不另外构建源码包 |
| 静态及来源 | Ruff、1,463 文件格式和 Git 空白检查通过；受改文档相对文件链接存在。源码／测试输入保持；a7／a8 四份原包和两份 manifest 哈希不变 |
| 独立只读 review | 最终 **218 passed**；额外核对嵌套 DTO wire 等价、固定 RunRef、Scope 漂移和模拟 Temporal 查询取消。上述 P2 已闭环，无剩余本批发现 |

最终证据位于 `dist/alignment-20261029/final/`。首轮私有包 `0.1.0a8+maintenance.79b4d53371e6affa` 留在上一级，不覆盖；两者都不是推荐公开制品。文档比较不等于运行其他框架的对等任务；独立 reviewer 无法再次打开具体 AgentScope overview，本会话主审已读取其开发版方法表，来源和此限制一并记录。

审查范围判定：第三方可执行 DTO／容器子类、隐藏捕获状态和任意深度数据仍遵循原可信适配器假设；不新增通用对象沙箱／净化协议。嵌套无效协程由生产方清理。真实 Temporal／数据库、模型质量、平台门禁、外部采用及全部 SDK 回归未在本批重验，均不以局部成绩代签。

## 后续优先级

1. **先完成当前入口的交付闭环。** 本批的所选回归／安装与审批恢复；包含维护修复的下一候选需单独版本、冻结包和平台门禁，不能套用原 a8 或把源码版本号当新制品身份。
2. **统一 Agent 展示事件。** 类型化模型／工具 delta、attempt 与原 Run 关联、背压／取消／重连及结束标记；复用原响应接收与采纳，不把未完成流当决策。优先一条文本 Agent＋工具链，再验收 Local／Temporal，不同时开发 UI／多模态／数据流。
3. **补通用受管理异步节点。** 从已有 Action／预算／审批／取消／回执／未知效果恢复派生节点契约，提供纯转换、检索和实际异步调用的默认及替换用例；再讨论共享状态／reducer／循环，避免直接 await 用户函数绕过权威。
4. **完善默认组合与真实适配。** 固定文本 Agent、语义 RAG、Plan／Team 任务，以现有 Provider／Embedding／工具／记忆组合验收；按具体用户模型和数据库接入补适配器／契约，不以数量追赶生态。
5. **随后推进数据治理和应用部署。** 索引增量／删除传播、记忆冲突／撤回、产物引用保留，之后统一服务观察与 OTel，再建设 UI／渠道和企业身份／成本／运维。每项分别需要设计、默认实现、替换、恢复和实际证据。

当前新增能力只覆盖第一项的工作区代码，不等于以上全部已完成。原 a8 制品、历史失败、旧版本兼容范围、原 S2／指纹资格均保持；本轮不推送、手动触发 CI 或公开发布，也不自动运行付费模型／启动新外部服务。
