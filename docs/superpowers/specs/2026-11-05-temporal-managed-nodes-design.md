# Temporal 通用受管理异步节点

基线 `8244e38`。落实用户已授权的下一批：复用 NodeExecutorRegistry 和 GraphNode.executor，在原 Temporal History 权威内运行，补恢复、安装、文档并仅本地提交。原制品／失败记录保留，不推送或公开发布。

## 范围与取舍

支持无状态静态图的串行、有界并行、Agent／executor 混合及 Team／Dynamic 的嵌套图。复用现有纯编译降低，不开放普通 Tool／Transform 图、循环或流式数据流。

父 Workflow 继续记录 child intent、额度和实际子 Run；executor 降低成私有单工具叶子请求，由原 native Workflow／TemporalRunState 执行。私有 `definition.kind=executor` 和单项 steps 仅描述节点，不是 AgentSpec，不填虚假 Provider。普通公共 Spec codec 不增加这一类型。

不在 Activity 内调用 LocalEngine，不新增 Workflow／Activity 名或另一套调度权威。不用脚本模型伪造工具提案。

首批预检拒绝节点图与实际 Session lineage／跨Turn历史、Coding composition、部署准入及父级完成验证的未选组合。普通无节点的已交付组合保持原行为；不据本批授予完整 H3／H5 或企业资格。

## 注册与发布

`TemporalRuntime(..., workflow_executors=registry)` 借用原 Registry 与客户端。Profile／JSON／TOML 沿既有同名组件工厂，默认 identity 可无模型运行；空 providers 只在显式节点注册时允许。普通 Agent 仍必须选择有效 Provider。

Manifest opt-in 增加 `workflow_node_protocol=1` 和 `workflow_nodes`（原 Registry 完整发布），私有 Tool Manifest 合入原 tools 证据，但不污染公开 ToolRegistry 或向模型提供名称。Temporal 仍按整 Worker release 固定全部注册；无节点配置不加字段。

节点必须启用原 ToolExecutionOwner，默认有界 owner 或显式注入，客户端资源继续沿 BuildContext.own／own_async 与 Assembly 排空、失败重试，不新增资源台账。

## 身份与隔离

内部叶子固定原 parent ID／epoch／release、节点 ID、child command／run、Scope、完整 input/config 和原发布。真实 Workflow 必须核对 SDK parent，不能把私有请求当独立公共根启动。

工具 envelope 携带原 `node_request`，Activity 核对私有 alias、原节点定义、参数、Tool／Registry manifest、Run／Scope／release 和父身份；真实 dispatch 仍由原 History admission 授权。普通 Agent、模型提案、公共工具或绑定不能选择私有 alias。宿主 allowed_tools、授权策略、审批和额度不因节点隐藏而绕开。

Schema 沿原 Temporal 的片段引用子集及无外部读取规则；不顺便扩大所有模型／Tool Schema 协议。输入和 config 保留独立根，输出允许所有有限 JSON，包括 null、false、0 和空字符串。

## 执行、恢复与完成

叶子不执行 Context、模型、自动记忆或模型完成验证。纯 History helper 提出稳定的原 kind=tool Action，复用审批、预算原子预留、稳定 effect_key、execute／reconcile／ACK 和未知效果分类。

Journal begin → execute → received → History tool_result_committed → ACK 顺序保持。不能在 Activity 内先验证 output_schema 而丢掉已发生的业务回执。History 保存实际结果后，等效果已知、ACK 与实际 handler end 义务排空，再校验 NodeExecutorSpec 和 GraphNode 的输出 Schema，成功或失败均不重写业务。

取消观察与业务取消分开；超时／Worker 丢失不等于实际 handler 停止。父级继续使用原 quiescent／unknown／pending ACK 门槛收口和释放 child cap。恢复优先查询原 Journal／reconciler，不调用 execute 伪造核验。

## 验收

- 离线确定性状态和 SDK／配置替换：完整 JSON、独立 config、Schema、零模型、预算、私有隔离、漂移与组合预检。
- 实际 Service：串行／并行／嵌套、审批期间 Worker 重启、写已发生但回执丢失、Journal 已收到而 History 未采纳、Schema 失败保留效果、取消后实际结束与关闭重试、原 namespace History replay。
- 无节点配置的默认 Manifest 不增加节点字段；所选旧普通 History 单独验证，新定义被旧 Worker 在业务 I/O 前拒绝。Coding composition 固定共享纯实现指纹，旧 Coding 任务需原包／匹配 Worker；不承诺任意旧 History 透明回放或跨版本迁移。
- 源码／目录外准确安装相同用例；唯一私有 wheel／sdist、运行依赖首用、原制品完整性、完整离线回归与文档分范围记录。模拟／跳过不代签真实服务。
