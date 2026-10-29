# Ordered framework alignment roadmap

**最新执行顺序（2026-10-29）：** 依据用户更新目标，先冻结[生命周期／事件／增量流第一批](../architecture/reviews/2026-10-29-stream-batch-freeze.md)，再降低已有入口的开发成本，随后验收固定默认任务；每批只交付一条主线。直接 Tool 节点草稿不混入本批，不按协议或适配器数量认定框架对齐。

## 当前复核：2026-10-29

当前基线为本地提交 `19dcc60`，远端仍为 `2f1b5b5`；包括多个 a8 后维护修复，与原 a8 两包分开。
对照全部 R01–R26 的分层状态及实际入口后，基础文本 Agent、常用编排、数据与恢复已有成体系实现，
但完整流式展示／多模态、通用图节点、现成集成、长期运行治理和对等真实质量尚未达到完整对齐。
`19dcc60` 沿既有 H2 契约交付 `AgentRun.subscribe_events()` 和事件数据校验。
后续工作区实现显式启用的模型文本／异步工具 JSON 增量与类型化结束事实，见[增量流指南](agent-stream-updates.md)与[本批验收](../architecture/reviews/2026-10-29-agent-stream-updates.md)；默认关闭，Local／Temporal 各自原权威不变。
当前范围不包含 reasoning／工具参数增量、多模态或 R09 节点数据流。原生文本Agent已追加正常／限额流、观察取消、审批期间Worker重启后重复审批及History重放的[真实Service／安装验证](../architecture/reviews/2026-10-29-temporal-stream-service.md)；高级组合、在途Activity故障与真实写／Journal仍待验收。
整体能力差距与后续优先级仍见[整体能力 review](../architecture/reviews/2026-10-29-framework-alignment.md)，不据此关闭整个 R22 或认定对等质量。

以下早期 roadmap 与按 dev 记录保留历史语义；其中 pending 不覆盖后来已交付的输入续接、
上下文压缩、记忆提炼等子集。当前逐项状态以 [R01–R26 清单](remaining-work.md) 为准，
不以新增 Protocol、适配器数目或局部测试通过宣称框架整体对齐／超越。

dev89完整原生Session历史子集已验收，沿既有纯Harness策略和原Local/Temporal权威补齐单Agent及RAG/Plan/Team的跨轮使用链路；每Agent配置和存储替换有实际恢复证据。旧默认保持，长会话History治理、真实模型质量、外部首次采用及对等框架比较仍开放。见[本批验收](../architecture/reviews/2026-10-13-session-model-history.md)与[完整能力清单](remaining-work.md)。下方早期基线按历史范围保留，不能用其旧缺口否定后续已验收增量。

Dev86 端到端任务评测子集已验收：源码5681 passed／447配置跳过（830.34s）、独立核心安装161；源码三次重复RAG24/24、Plan15/15、Team15/15及安装CLI／SDK例子、旧85默认／原Plan回执兼容与298模块一致通过。复用原执行权威，新增最终模型请求可见引用、实际成员／工具回执、独立Embedding计量和观察式恢复；2项Important／1项Minor经有效RED统一修复。离线／MockTransport不构成真实模型质量；完整H3／M1／R01–R26及外部采用保持开放。见[任务评测指南](task-evaluation.md)与[本批验收](../architecture/reviews/2026-10-13-task-evaluation-chains.md)。

Baseline: dev46 increment, 2026-10-10. The user approved this order after
the capability checklist. Completion requires default behavior, extensibility,
lifecycle/recovery, installed documentation and real evidence per component.
Adding a Protocol or counting passing tests alone does not establish parity.

The [dev23 holistic review](../architecture/reviews/2026-10-08-agent-framework-alignment.md)
sets the architectural guardrails. dev24 closes its three reproduced runtime
issues through [shared decision/evidence rules and recent Session projection](shared-model-context-contracts.md).
dev25 delivers native Agent/sequence H1a; dev26 extends the same six roles to
Local Graph/Team/Dynamic/nesting. dev27 adds selected Session backends and allowed namespaces with actual-address admission. dev28 adds explicit Facts/Knowledge namespace views and source-bound validation. dev29 adds pure Agent completion verification with durable receipt-based feedback. dev30 adds fixed Agent limits under mandatory host caps. dev31 delivers Local stateless Agent/Runtime, independent hosting, pure observation and retryable closing. dev32 delivers colocated native/sequence durable Session/Turn admission and binding revisions. dev33 delivers native/sequence Temporal Agent entry with common async attachment, pinned RPC dispatch and client detach. dev34 adds the registered advanced Temporal facade and actual child control references. dev35 adds colocated Local composite Session Turns with original member bindings and atomic final save. dev36 adds authorized composite root namespaces with separate host resources and original binding checks. dev37 adds root Profile declarations and an installed Session starter with original Profile/Turn reconnection. dev38–39 add remote Session routes; dev40–42 add native/sequence Local managed rule memory, historical summaries and model-selected memory. Temporal bindings, remaining resource roles/selection, advanced/Temporal memory defaults and semantic data quality remain open. dev43 adds recommended Local combinations, deterministic reference excerpts and original-Run artifact projections; full H3 remains open. The [remaining-work audit](remaining-work.md) maps the current gaps;
test coverage and adapter counts alone do not establish AgentScope parity.

Continue the approved order with a cohesive Agent/session entry path, immutable
per-Agent capability bindings and shared backend acceptance cases. Providers,
Context/Memory/RAG/Workspace and service features must compose through that path;
their availability as separate adapters does not complete default usability.

dev44 extends managed compression/offload to Local graph/Team/dynamic/nested Agents and explicit Temporal registration. Preparatory I/O and atomic dispatch admission remain under original Run/History authority, with actual worker recovery and replay evidence. Advanced/Temporal automatic memory writes, semantic defaults, remote artifact defaults and complete H3 remain pending; this increment does not establish framework parity.

| Order | Deliverable | Status / gate |
| --- | --- | --- |
| A1 | Models and typed-tool foundations: native Responses, inference/keyword bridge, reusable managed compatibility scenarios | dev22; subset and evidence in [guide](sdk-model-tools.md) |
| A2 | Unified middleware/events/input continuation, useful default tools and container Sandbox/Workspace | dev23 delivers opt-in middleware and durable-event observation; dev83 delivers a restricted local Docker Sandbox subset; input continuation, broader default tools and other environments remain pending |
| A3 | Managed automatic context compaction, remote artifacts and semantic memory/RAG defaults | pending; source/Scope/budget/TTL plus fact retention and answer/citation quality |
| A4 | Freeze complete final-config real business/planning/RAG/recall tasks, repeat with domestic/international models | pending; explicit credentials/call/output/time bounds and retained reports |
| B1 | Agent Service/streaming API, TUI/Web UI, sessions and resource library | pending; installed application path and external developer acceptance |
| B2 | Channels, background jobs/wakeup/indexing, OTel/metrics/diagnostics | pending; lifecycle/reconnect/idempotency and end-to-end deployment evidence |
| C1 | Local/Temporal feature contracts, multi-process, capacity/History retention and deployment versions | pending; backend capabilities/refusals and real fault/upgrade acceptance |
| C2 | Enterprise identity/ACL, cost/tenant quotas, retention/migration/backups and restore tooling | pending; independent enterprise acceptance, not inferred from SDK scope |
| D | Matched AgentScope/LangGraph scenarios and business-effect recovery comparison | pending; same models/tools/tasks, integration effort and fault outcomes |

For A2, settle the shared input/result/presentation-event semantics and per-Agent
bindings before exposing service APIs or adding more independent templates.
Retain committed Run facts separately from model deltas. For A3, managed async
preparation supplies pure context policies; automatic summaries or memory never
become hidden model calls in pure hooks. Ship versioned recommended defaults for
new releases while preserving original accepted releases.

Each increment must include an installed end-to-end user scenario and one real
component replacement, measuring onboarding, diagnosis and recovery alongside
correctness. A4 remains the complete repeated quality gate; earlier relevant
quality evidence is retained when explicitly configured, and untested live
quality is reported as such. No benchmark or enterprise claim follows from this
roadmap review.

Each layer delivers a role contract, a minimal default, configuration and direct
injection examples, lifecycle/identity/errors, reusable conformance tests and
operator diagnostics. Offline defaults do not pretend to be real intelligence.
Advanced adapters stay optional; original accepted releases remain recoverable.
See [current support](implementation-status.md), [M1 gates](m1-acceptance.md) and
[existing live trial](live-model-quality.md). No parity/superiority claim is made.

## AgentHarness design mapping

The [target AgentHarness](../architecture/viewpoints/harness-runtime.md) implements
this roadmap through five coherent stages. Remaining H1 capability bindings and
H2b remote Session semantics and remaining Temporal binding roles are the next A2 dependencies; colocated native/sequence H2b1 and composite H2b2, native Temporal H2c1 and registered advanced Temporal H2c2 are delivered. H3 is A3 managed default chains;
H4 delivers the remaining A2 environment/cooperation work; H5 spans B1/B2/C1/C2
service and backend governance. A4 real quality evidence runs throughout rather
than waiting until all infrastructure exists. D parity requires matched experiments.
This preserves the approved order while making per-Agent composition concrete.
The [binding contract](../architecture/specs/agent-capability-binding-contract.md)
fixes declarations, host policy limits, original-release recovery and backend refusal.
The [Facade/Session contract](../architecture/specs/agent-facade-session-contract.md)
sets H2 prerequisites: execution hosting independent of waiters, observation-only
wait/cancel boundaries, durable reject-if-busy Sessions, binding revisions and
owned/borrowed drain/reattach. Durable Turn FIFO is a later opt-in capability;
initial queue requests are refused. [Naming and source comparison](../architecture/reviews/2026-10-08-agent-harness-facade.md)
uses the user-selected local AgentScope 2.0.10dev commit rather than inferring
behavior from the previous v2.0.9 overview. [H1a/Local H1b](agent-bindings.md) cover native Agent/sequential Workflow and
Graph/Team/Dynamic/nesting with six selectable roles and versioned assembly.
dev27 adds Local Session backend/namespace/address admission; dev28 adds scoped Facts/Knowledge; dev29 adds pure completion verifier bindings. Temporal bindings, other resource selectors, H2 SessionAdmission and
full Agent/Runtime Facade remain pending. Local stateless H2a is delivered in dev31; no parity is inferred.

Dev44 extends Basic/Knowledge data context to Local graph/Team/dynamic/nesting and registered Temporal Agent children. Actual Workflow History owns auxiliary phase evidence, with single-attempt writes/summaries and immutable snapshot validation. Advanced automatic memory writing, final default-model semantic quality, environment capabilities and full H3 are still open; no AgentScope parity claim.

Dev45 closes the Local advanced rule/model-selected memory/default composition gap, with node-scoped original evidence, terminal root/child recovery and process-death coverage. Temporal memory writes and semantic memory/task quality remain separate pending gates.

Dev46 adds explicit Temporal History-managed grounded memory and five scoped per-Agent binding roles across actual composite members. Worker recovery/replay evidence does not establish semantic memory quality or whole-framework parity. [Scope and acceptance](temporal-memory-bindings.md).

当前 dev62 增量已把 Temporal 纯完成验证接入原节点／回执／记忆链路。dev58–61 的 Facts／Knowledge 范围、History Sessions 和数值限制，连同 verifier 构成八类 Temporal 绑定。下一依赖为 DecisionPolicy 与外置 Session／环境角色、输入续接和治理；完整 R01–R26、A/B/C/D 门槛继续以剩余清单为准。完成绑定子集和 scripted 恢复不代表 AgentScope 整体对齐或真实质量通过。

Dev63接通原生及高级Temporal纯DecisionPolicy，形成九类每Agent绑定。默认与纯策略可替换、原History恢复闭环分别验收；外置Session/环境角色、H3质量、H4/H5和对等外部采用仍待交付，不能以绑定数或回归测试推断整体对齐。


dev65 增加 Temporal Session 有界读依赖，仍缺外置会话写和跨 Turn 路由；不能据此宣称完整第十类绑定或 AgentScope 整体对齐。


Dev67 adds original Temporal Parent root/private Session trees with source-once data,
explicit replaceable topology, fixed per-member resources and actual-handler end evidence.
This narrows the distributed persistence gap for Graph/Team/Plan/DAG/nesting; it does not
establish AgentScope parity. Remaining configuration, environment/Runner, lifetime and
enterprise governance, live-quality and external-adoption gates remain in
[the capability list](remaining-work.md). Final delivery evidence is separate from
scripted provider tests in [dev67 acceptance](../architecture/reviews/2026-10-11-temporal-session-trees.md).
