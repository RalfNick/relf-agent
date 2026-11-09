# 自定义节点扩展验收

基线 `5e2b57e`。沿既定 R25 扩展验收方向，补 NodeExecutor 的可运行检查与参考实现。用户已要求持续推进、不反复中断；本批选定范围沿原能力清单，不增加执行语义。仅本地提交、单次跳过钩子，不推送／公开发布，保留原包与失败。

## 选择

既有下一方向包括复杂 Temporal 增量流证据、节点扩展验收和新的编排语义。本批选择扩展验收：现有 Local／Temporal 节点注册已经实现，第三方仍缺少安装后的自检和独立可编辑组件。复用 AdapterContractSuite 比新增执行或流协议更小；继续保留其他方向，不宣称完成完整 R25。

## 固定接口

新增 `node-executor`、版本 `1`、profile `core`，N01–N10：

1. identity-and-port：结构化 identity 与实际异步 execute，注册／读取固定描述。
2. finite-json-and-config：Local 实际图转发完整 JSON／独立 config，接受 null／false／0／数组／文本输出。
3. input-schema：非法输入不启动处理器。
4. config-schema：非法配置不启动处理器。
5. completed-output-schema：已保存实际结果后输出 Schema 拒绝，保留原观察和消费。
6. identity-drift：原注册身份变化后不调用处理器。
7. method-drift：原入口变更后不调用替换处理器。
8. handler-errors：真实处理器异常不能得到 succeeded，不冒出或记录原始敏感异常。
9. approval-budget-and-reopen：原额度拒绝、审批、重复命令和 SQLite 关闭重开；读取型组件只调用一次。
10. cancellation-and-ownership：取消真实低层 LocalEngine.drive 调用方，沿原语义请求业务取消；实际处理器未结束时仍持有原责任；关闭拒绝、实际完成后原对象安全重试；借用组件不被隐式关闭。

新增 `NodeAdapterFixture.prepare(case_id, workspace)` 返回 `NodeContractSession`（可异步）。Session 提供 component、最多16个 `NodeContractResource(resource, asynchronous=False)` 及可选 configure、inject_fault、pause、audit、reopen。configure(kind, data) 支持 output（data.result）；configure reset 仅为可选管理辅助，本 Suite 不调用或认证它。inject_fault 支持 identity-drift／method-drift／handler-error／reset。除 audit／pause 外管理回调仅返回完成的 None；pause('execute') 返回 `NodeContractPause(wait_entered, release)`。reopen 在关闭原 Engine 后重连原组件、保留其 identity 与计数；audit 仅返回固定整数计数 execute_calls／reconcile_calls／close_calls，不得给 verdict。

Suite 构造原 NodeExecutorSpec（probe、read_only、cost=2），将 fixture 的实际组件注册后，使用原 LocalEngine／SQLiteStore／GraphWorkflowSpec；没有 Provider、替代状态机或 fixture 提供的 Run／Action 回执。原 Store、预算和结果决定判定；fixture 仅提供可控业务数据、故障及计数。缺少所需回调为 not_verified，不能视作通过。错误和证据沿原脱敏／限额；关闭失败交原 AdapterContractCleanupPending 机制，取消须排空原任务及资源后才能释放 workspace。

## 默认实现与边界

独立 SQLite 参考组件保存调用输入、输出配置与计数，未继承框架 Node 实现。`offline_node_fixture()` 显式选择，本批不自动连接模型／远程库。CLI `relf-check-adapter --role node-executor --offline` 复用原入口；不提供新的动态 Python 插件加载器。另提供可复制的参考示例，展示替换组件与管理回调。

原 Knowledge／Session／Facts／Model catalogs、status codes、摘要和默认 CLI 均保持。新 catalog 单独确定 requirements／observation allowlist／digest。

只认证 fixture 配置下的 Local 只读核心链路，不认证任意业务逻辑、写幂等／unknown reconciliation、Temporal、真实模型质量或独立外部采用。审查新发现的 Temporal 默认16槽饱和导致无启动调用失败，按现有 fail-closed 行为单独记录；背压重试涉及原独占准入与停止证据，不在本批改阈值或增加重试协议。

## 验证

真实 RED 后实现：catalog／dispatch／CLI；独立参考的10检查；故障、缺失回调、伪造 verdict、非法异步返回、关闭取消／重试；原四角色摘要不变。验证实际 Local Graph 审批／重开和取消，源码与目录外唯一私有 wheel 同ID；sdist 产品一致和无 pytest 运行依赖 smoke。最终执行完整离线回归，任何失败保留并按实际范围记录，不拼接成全轮通过。最后同步指南、R25及交付记录并仅本地提交。
