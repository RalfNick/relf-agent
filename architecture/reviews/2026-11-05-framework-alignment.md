# AgentScope／LangChain／LangGraph 能力复核

日期：2026-11-05。RELF 源码基线为 `e317a48`，位于已推送的 `codex/callable-preview-fixes`；公开 main、原推荐私有组合、Local 节点验证包和历史 Alpha 是不同快照，见[当前交付](../../docs/current-delivery.md)。本次没有模型或跨框架对等 benchmark。

## 判断

基础文本 Agent、工具、Session、常用静态／动态编排、Team、记忆、RAG、上下文压缩与业务效果恢复已形成体系。当前主要差距是组合覆盖、首用成本、生态、完整应用运维和证据范围。无需推翻 Harness／执行／数据分层，也没有证据支持整体达到或超过其他框架。

对比的是 AgentScope 官方 Python 主仓库当前 main（README 自述 2.0），以及 LangChain／LangGraph 当前官方文档；未核验 AgentScope 最新发布 tag，不沿用旧 2.0.9 作为当前全貌。独立 Service、Studio、LangSmith 等产品与开源 SDK 分开看。

| 方面 | RELF 已有 | 差距与优先方向 |
| --- | --- | --- |
| 编排与状态 | 顺序、图、有界并行、动态 DAG、Plan／Team、嵌套；Local 通用异步节点 | Temporal 仍拒绝 executor 节点；循环、reducer、quorum／first-success 与类型化工作流状态未完整。LangGraph 的普通函数节点、循环和动态 fan-out 更丰富。下一次编排能力增量应先做现有节点的后端同契约，单独验收恢复，再考虑新的状态语义。[Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) |
| 增量与流 | 耐久事件游标、类型化模型文本及显式异步工具 JSON 进度 | reasoning／工具参数／多模态和高级组合实际服务证据不完整；逐记录 Workflow 数据流未交付。可参考 LangGraph 从事件向消息、状态和子图输出投影的设计；展示继续不取得调度权。[Event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming) |
| 多模态 | 当前主模型链路为文本与工具 | 图片内容块、媒体来源与访问限额、逐协议验收未交付；音视频／实时更远。LangChain 有统一多模态消息；AgentScope 展示图像／音频与实验性实时能力。宜先独立设计图片来源契约。[Messages](https://docs.langchain.com/oss/python/langchain/messages)、[AgentScope README](https://github.com/agentscope-ai/agentscope/blob/main/README.md) |
| 默认组件与生态 | 可替换 Provider、ToolSource、Session／Facts／Knowledge、Embedding、Vector、RAG 及版本化配置 | 搜索／浏览器工具、更多业务连接器、持续 MCP Session／OAuth 和索引生命周期不足；高级记忆与 Artifact 阶段仍有内置基类约束。LangChain 的集成目录覆盖更广。优先验证第三方替换的完整使用链路，不能以 Protocol 数量代替易用性。[Integrations](https://docs.langchain.com/oss/python/integrations/providers/overview) |
| 应用与运维 | starter、资料助手、有限 HTTP／A2A 控制、审批恢复、部分保留与备份 | 缺统一应用控制台、通用 OTel、托管资源池／后台作业、完整企业身份与凭据代理。AgentScope 的 Service 有独立应用层能力；这属于另外的交付面，不应全部算作 SDK 差距，也不在本次维护中补平台。[AgentScope Agent Service](https://github.com/agentscope-ai/agentscope/blob/main/README.md#agent-service--all-you-need-to-build-your-app) |
| 真实质量与采用 | 四条有限参考业务链有模型成绩，恢复／审批有本地及所选实际服务证据 | 自主规划、复杂重规划、长期记忆冲突／撤回、多厂商最终配置和外部开发者采用仍缺充分证据。应使用同模型／工具／服务比较接入与故障结果；LangGraph 自身已有持久执行和副作用幂等要求，不能称它缺乏恢复。[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) |

## 本轮先修复的接入问题

1. 节点 input/config 的独立 `$defs/$ref` 在 Tool 包装后引用根改变，合法 Schema 无法执行。
2. 若干公共 Schema 边界默认读取外部文件／网络，未固定内容可改变相同 Manifest 的校验结果。
3. Embedding 深 JSON 或关闭的借用 HTTP 客户端会冒出原生异常。
4. 资料助手命令引号不完整会终止整个聊天。

实现与实际成绩见[本批维护验收](2026-11-05-framework-boundaries.md)，配置语义与升级边界见[Schema 指南](../../docs/schema-validation.md)。本轮只修复已有能力，不增加新的编排、模型协议或执行后端。

## 后续顺序

先让现有常用路径在源码、准确安装和恢复中保持一致，再单独补 Temporal executor 同契约及复杂组合流证据；随后是统一增量类型、默认集成与结构化扩展套件。循环／reducer、多模态和应用平台应分别定范围，不合并成一次持续扩张的开发批次。真实质量和独立采用贯穿每批；未验证项目保持开放，见[R01–R26](../../docs/remaining-work.md)。
