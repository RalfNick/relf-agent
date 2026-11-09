# 关闭未完成的安全诊断

本批仅补关闭错误的观察信息，与 Temporal 容量修复共同验收。原 Local／History 执行权威、关闭顺序、资源责任、取消和恢复语义保持；不新增控制命令或状态机。

## 方案和边界

原 `CloseIncomplete(report)` 的 code、message 与 report 对象／类型保持。增加 keyword-only `diagnostics=None` 和只读 `.diagnostics`，每次返回独立 JSON 副本。没有元数据的原调用显示 unknown，不从任意 report 正文猜测阶段或泄露业务内容。

固定 schema_version=1、state=incomplete；authority 为 local／temporal／unknown，ownership 为 owned／borrowed／mixed／unknown。stage 为 unknown、run_drain、rpc_drain、construction、execution_drain、handler_drain、end_ack、worker_start、worker_stop、authority_close、resource_close。blockers 仅允许 run／rpc／construction／handler／thread／end_ack／worker／resource 的实际非负整数计数，范围0至2**63-1，拒绝布尔及不可呈现的巨大整数；未知计数省略，不冒充0。retry_action 固定 retain_original_instance_and_retry_close。

内部 `make_close_diagnostics(*, authority='unknown', stage='unknown', ownership='unknown', blockers=None)` 构造脱敏快照；`enrich_close_diagnostics(error, **options)` 保留已有具体诊断，仅补未知字段及额外实际计数。无原始 report／异常正文、Scope、Run ID、端点、路径或任意对象 repr。

接入 Local／Temporal Facade 的原 drain 和 owner close 阶段、Temporal 构造任务／线程等待和 Assembly 的执行排空／Worker 结束／owned 资源清理。`handler` 统计原 Context／Tool owner 托管操作，可能包含仍等待原 History 准入的新节点调用；不能据此推断业务处理器已启动、请求已派发或效果存在，派发仍看原 History／效果事实。结束ACK阻塞按原通知责任独立呈现。CLI 在 CloseIncomplete 或原 RuntimeBuildError 的直接 cause 精确为 CloseIncomplete 时追加诊断，保留外层原 code／message／cleanup；不遍历任意异常链，其余错误格式保持。

选取增量错误快照，避免替换已有 report DTO。没有为每个 Runtime 新增状态属性；取消观察仍抛原 CancelledError，原工作继续受原对象管理。非 CloseIncomplete 的旧异常保持原类型；不认证所有未接入的关闭来源。

## 恢复与验证

先用反例证明 legacy report 保留／脱敏、元数据副本隔离、计数类型与 unknown 语义；真实 Local 工具阻塞、取消关闭观察、原 Coordinator 和同实例重试；原 Temporal RPC 所有权、Builder 任务／线程、Assembly owned 资源与Worker清理。只观察已有事实，不通过诊断释放或重发任何业务。

仅在目录外准确安装与相关恢复回归后验收。部署／Coding 固定的 Builder／Assembly／Facade 源码指纹会变化，旧选定任务继续使用原包／匹配 Worker；普通默认 release 另行字面核对，不移除原指纹验证。原制品、历史失败和并行网站改动保持。
