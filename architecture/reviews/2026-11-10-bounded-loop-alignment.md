# 框架后续对齐：有界迭代组合

2026-11-10，基线为仅本地提交的 `085c0f5`。上一批已补有限列表FanOut，准确候选、原默认组合及本轮源码分开，见[当前交付](../../docs/current-delivery.md)。

本次再次参考[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)、[LangChain Streaming](https://docs.langchain.com/oss/python/langchain/streaming)和[AgentScope官方main概览](https://github.com/agentscope-ai/agentscope/blob/main/README.md)。这些官方入口分别描述条件控制／状态合并、模型与工具等流式投影，以及Agent／团队／上下文／工具和服务组合。它们的完整能力不由RELF的一个默认策略等同，独立Service／商业平台亦不混入开源SDK排名。

## 本批选择

| 方向 | 当前依据 | 决定 |
| --- | --- | --- |
| 有界执行／检查／修订 | 原Dynamic已有revision、纯Verifier replan、逐轮子Run、预算与恢复；默认组合需要应用自己写 | 提供显式BoundedLoopPolicy，同时实现原plan／verify，不增加执行权威 |
| 类型化工具参数增量 | 原文本／异步工具进度已具备；原模型流DTO、wrapper指纹和展示v1不能直接扩成新协议 | 独立新端口／wrapper／v2策略，另批实施；本批不改旧流入口 |
| 默认业务工具集成 | 固定HTTP仅POST／GET、204空正文明确不接受；MCP发现已有，持久连接仍缺owner | PUT／PATCH与显式空204可以独立补齐；持久MCP生命周期另定，不混入循环 |

BoundedLoopPolicy只提出原单节点DAG并核验已采纳结果；停止条件使用原BranchCondition和canonical JSON。结果ID保持不透明，由执行权威提供有序history，避免把后端的ID拼写固化到业务策略中。真实执行测试另外核对逐轮身份、审批和去重。

这只是“每轮执行一个已有成员，检查是否结束”的默认组合，不是通用带环图、共享可变状态reducer、无界循环或更强模型规划。完整增量流、多模态、默认集成、长生命周期治理、外部采用及对等任务质量仍是差距。

设计见[规格](../../docs/superpowers/specs/2026-11-10-bounded-loop-design.md)，本批实际结果见[验收](2026-11-10-bounded-loop.md)。本批按所选范围完成实际验证，分层成绩以验收记录为准，不把接口或测试数量视为整体追平的证据；原M1／R01–R26及历史门槛保持。
