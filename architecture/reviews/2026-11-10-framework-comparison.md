# 当前框架能力对比与下一批范围

2026-11-10，只读复核 RELF 开发源码 `3965925` 及本次读取的官方文档。源码、准确私有包、原推荐组合、公开 main 和官网各按原快照解释；本文不运行对等 benchmark，也不新增平台、模型质量或企业生产资格。

## 官方项目定位

| 项目 | 官方当前能力与定位 | 对 RELF 的实际启示 |
| --- | --- | --- |
| LangChain＋LangGraph | LangChain 提供 `create_agent`、模型／工具及 middleware；LangGraph 提供状态图与持久编排。Graph API 支持 typed state、字段 reducer、Send 动态分发、Command 更新／路由／恢复，以及条件循环。Functional API 用 entrypoint／task 保存任务结果 | 不能把 checkpoint、审批、动态分发或循环继续笼统列为 RELF 独有能力；RELF 的有限默认模式还不等于通用共享状态图 |
| AgentScope | 官方 main 列出 ReAct、Python／MCP／Skill 工具、多模型、上下文压缩与结果卸载、可替换记忆、沙箱和统一事件；另有团队、RAG、渠道和 Web UI 等 Service 组合 | SDK 原语以外，现成组件、默认组合和完整应用体验仍需持续补齐；不能把 SDK 与独立服务覆盖混为同一验收 |
| AutoGen | Core 提供消息／事件、本地及实验性分布式 runtime；AgentChat 提供群聊团队、handoff、终止条件及 Agent／Team 状态保存与加载；Extensions 提供模型、MCP 和本机／Docker 代码执行。GraphFlow 是实验性有向图流程。官方现已归档、停止维护，推荐 Microsoft Agent Framework | 可参考 Core／AgentChat／Extensions 分层、团队与交接；对话状态保存不等于业务效果恢复，实验性流程和分布式运行时也不能直接视为企业验收 |

上述能力依据：[LangChain 概览](https://docs.langchain.com/oss/python/langchain/overview)、[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)、[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)、[AgentScope 官方 main](https://github.com/agentscope-ai/agentscope)、[AutoGen 官方 README](https://github.com/microsoft/autogen)。本次 AgentScope 依据 main，不能当作某个稳定发行已验证的完整能力；AutoGen 的归档说明不构成对 Microsoft Agent Framework 生产能力的独立评测。

AutoGen 的具体接口见官方 [Core 通信](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/framework/message-and-communication.html)、[分布式运行时](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/framework/distributed-agent-runtime.html)、[AgentChat](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/index.html)、[Swarm 交接](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/swarm.html)、[终止条件](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html)、[状态保存／加载](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/state.html)和[GraphFlow](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/graph-flow.html)。GraphFlow 支持顺序、并行、条件和循环，但官方明确标为实验性；[MCP](https://microsoft.github.io/autogen/stable/reference/python/autogen_ext.tools.mcp.html)与[代码执行](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/components/command-line-code-executors.html)属于扩展组件。

SDK 与平台／开发工具分开比较：[AutoGen Studio](https://microsoft.github.io/autogen/stable/user-guide/autogenstudio-user-guide/index.html)是可视化构建工具，[AutoGenBench](https://github.com/microsoft/autogen/blob/main/python/packages/agbench/README.md)是独立评测工具，按各自版本支持范围解释；同样不把 AgentScope Service 或 LangSmith 的全部部署／观察能力计入 SDK 已对齐范围。

## RELF 已有能力与主要差距

RELF 的 Agent／工具、Session、上下文、记忆／RAG、静态图、Team、动态 DAG 和嵌套已经形成可组合实现；Local 与 Temporal 保持各自唯一执行权威。近期的 [Fan-Out](2026-11-10-fan-out-planning.md) 和 [BoundedLoop](2026-11-10-bounded-loop.md) 已按各自有限源码／准确安装、恢复及所选真实 Temporal 范围验收，不能继续描述成“没有动态分发或迭代能力”。原推荐包与历史 Alpha 不自动包含这些增量，准确入口见[当前交付](../../docs/current-delivery.md)。

| 方面 | 当前已具备 | 仍缺少或未证明 |
| --- | --- | --- |
| 编排 | 有限列表分发、可选汇总成员；最多32轮执行／检查／修订默认策略；原审批、预算与恢复 | 通用带环图、字段级共享状态合并、通用 Functional API；现有汇总成员不是共享 reducer |
| 交互 | 持久事件、模型文本及显式工具 JSON 进度、原权威结束事实 | 模型工具参数／推理块增量、复合 Run 聚合与子图来源、统一多模态交互 |
| 默认接入 | 多模型协议、数据端口、Python／MCP／HTTP／CLI、可替换受管理节点 | 更多经过完整应用验收的默认集成；同一份定义下所有 Local／Temporal 组合并未对齐 |
| 使用与成熟度 | 离线 starter、配置工厂、独立安装和故障恢复证据 | 外部开发者独立采用、持续业务质量和同模型／任务／工具的框架对等实验 |

LangChain 当前流文档推荐 v1.3 引入的 typed event projections：消息、工具调用、状态与子图可分别消费，工具参数块与工具执行生命周期也分开。RELF 现有文本／工具进度不能据此视为完整对齐，参见[官方 Event streaming](https://docs.langchain.com/oss/python/langchain/event-streaming)。

LangGraph 的持久化区分线程检查点和跨线程 Store；其文档也要求开发者处理重执行的副作用及幂等性。RELF 显式审批、Action 身份、unknown 核验有实际业务价值，但没有对等故障实验支持可靠性更强，也不保证任意外部写恰好一次，参见[官方持久化](https://docs.langchain.com/oss/python/langgraph/persistence)与[节点重执行要求](https://docs.langchain.com/oss/python/langgraph/graph-api#re-execution-and-idempotency)。

## 本批只补固定 HTTP 写接口

本批选择已有 HTTP JSON ToolSource 的显式 PUT／PATCH 与严格 opt-in 空204。这能减少业务系统更新接口的自定义适配代码，复用原 ToolSource、ToolPolicy、稳定 effect key、审批及实际线程关闭；它是默认集成改善，不是通用编排、共享状态或完整流协议的替代。

范围为固定 URL／方法／头，POST／PUT／PATCH 沿原 canonical JSON 正文；仅 GET 使用查询映射。`allow_empty_204=False` 保持旧拒绝，显式开启时仅接受无异常 framing 的实际空204并继续校验 null Schema。不得根据 HTTP 动词推断业务幂等性或放宽授权，不增加 DELETE、动态目标、自动重试或新执行权威。设计见[固定 HTTP 写方法](../../docs/superpowers/specs/2026-11-10-http-write-methods-design.md)。

本增量已按[所选范围验收](2026-11-10-http-write-methods.md)：源码／准确安装各280项、运行依赖9条与所选旧POST／GET元数据一致；实际loopback覆盖Local审批重开／丢失响应／取消关闭。本批不新增真实 Temporal Service、完整框架或模型质量资格。模型参数流、通用共享状态和持久 MCP 生命周期各自另定范围，原制品、历史失败与并行网站内容保留，不推送或公开发布。
