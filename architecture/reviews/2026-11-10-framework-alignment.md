# AgentScope／LangChain／LangGraph 后续对齐

2026-11-10，开发源码基线 `aa77b90`。最新已登记推送为开发分支 `codex/callable-preview-fixes` 的 `ec23ae5`／`aa77b90`；本地安装包、公开main、官网和历史Alpha各按原快照解释，不把新源码资格授予原包。

## 当前判断

RELF的文本Agent、工具、Session、常用图／动态编排、团队、记忆／RAG与效果恢复已成体系。近期已补所选Temporal通用异步节点、默认节点容量背压、关闭诊断、结构化节点接入检查及两个公共校验边界。旧对比把Temporal executor整体列为缺失，已不适用于当前源码。

当前主要差距仍是通用循环／共享状态合并、完整模型／工具／子图增量、多模态、默认集成、长生命周期运维和外部采用证据。没有对等任务实验支持整体达到或超过成熟框架。

| 方向 | 官方参考与RELF现状 | 本批边界 |
| --- | --- | --- |
| 动态批处理 | [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)有动态分发和状态合并；RELF已有DAG、成员子Run及并发控制，本批前列表分发仍需自写Planner | 补显式FanOutDAGPlanner与配置／示例；不实现共享可变状态或循环 |
| 增量交互 | [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming)提供不同流模式和子图来源；[AgentScope事件文档](https://docs.agentscope.io/en/versions/2.0.12dev/building-blocks/message-and-event)将消息与前端事件区分 | RELF已有文本／显式工具进度、游标和限额；模型参数片段、复合Run聚合与跨Run游标另定范围 |
| 默认组件 | [AgentScope官方main概览](https://github.com/agentscope-ai/agentscope/blob/main/README.md)列出模型、工具、上下文和服务组件 | RELF应继续补常用组合的默认实现和完整接入路径；本批不顺带新增HTTP写方法、MCP长连接、沙箱或平台 |

本次参考官方main／文档，AgentScope事件页重定向到 `2.0.12dev`，不能把开发文档等同最新稳定发行。独立Service／Studio／LangSmith等产品与开源SDK分开；没有模型质量或性能对等benchmark。

## 本批选择

先提供有限列表→并行Worker→可选汇总成员的默认Planner。输入按原ValueRef绑定，每项拥有稳定DAG节点／子Run；输出是稳定ID映射或汇总成员结果。只提供原方案提案，不自行派发、重试、结算或保存第二套执行状态。

显式装配避免改变默认整表身份，Local／Temporal继续各自唯一权威。worker／汇总成员仍可替换为已有Agent或受管理Graph组件，不要求应用继承新的Agent基类。

设计见[本批规格](../../docs/superpowers/specs/2026-11-10-fan-out-planning-design.md)，实际证据另见[本批验收](2026-11-10-fan-out-planning.md)。本批已按上述有限范围完成源码、准确安装、恢复与所选真实服务验证；实际成绩以独立验收记录为准，不把有限子集扩大为整体能力；完整R01–R26、更多组合、外部采用和真实智能质量继续开放。
