# NodeExecutor 核心扩展检查验收

日期：2026-11-09。源码基线 `5e2b57e4cede733c9141e0b5c253b25ad18fd42d`。本批新增 R25 的有限扩展检查，不增加执行后端或状态机，不推送／公开发布；原制品和失败记录保留。

## 交付范围

显式 `node-executor`／contract version `1`／profile `core`，N01–N10 通过原 NodeExecutorRegistry、LocalEngine、SQLiteStore／Tool Action 核对结构端口、有限 JSON／独立 config、输入／输出 Schema、原入口漂移、异常 unknown 保留、审批／预算／重复命令／关闭重开，以及真实低层 drive 调用取消后的处理器与资源责任。

新增 NodeAdapterFixture／NodeContractSession、NodeContractResource／Pause；fixture 只准备实际组件和可控测试供应端，不给 verdict 或 Run 回执。默认构造／不传 fixture 不运行数据 I/O，缺所需管理能力为 not_verified。显式选用的内置 SQLite 参考和[可编辑组件示例](../../examples/node_executor_contract.py)都未继承框架 Node 实现；管理回调不是新的执行权威。使用见[指南](../../docs/node-adapter-contracts.md)，设计及任务边界见[规格](../../docs/superpowers/specs/2026-11-09-node-executor-contract-design.md)／[计划](../../docs/superpowers/plans/2026-11-09-node-executor-contract.md)。

Suite 的 probe Spec 固定只读、cost=2，验证 fixture 测试配置的接入链路，并非认证每个业务节点必须接受任意 JSON。专用业务节点、真实外部效果及质量需要自己的受控配置与证据；本批不关闭完整 R25。[机器记录](../../evals/results/relf-node-executor-contract-20261109.json)保存准确版本、SHA与分项结果。

## 验证记录

| 验证 | 结果及边界 |
| --- | --- |
| 冻结源码 | 31模块 **815 passed，0 skipped**，约92.51秒，`-W error` |
| 准确安装 | 同815个ID **815 passed，0 skipped**，约88.63秒；目录外 site-packages，无 checkout/src 或 PYTHONPATH |
| 独立组件 | 默认 SQLite 参考及另写的普通 Python 组件都实际通过全部10检查；例子无持久业务后台，不冒称跨进程供应方数据恢复 |
| 仅运行依赖 | **14条命令通过**；无 pytest／Temporal；CLI not_run、显式离线10项、独立示例及重建 sdist 再运行；461个产品重建内容一致 |
| 所选兼容 | 旧 SDK `0.1.0a8+tnodes.3675891f64d0664f`、当前源码及准确安装的七个旧 suite digest 和默认 Temporal Node Profile release 相同；没有实际 Service 或任意 History 迁移资格 |
| 独立审查 | 核心／参考76项独立通过，另手写复现原问题与恢复边界通过；最终固定 Local 读取型范围内无剩余阻塞 P1／P2 |
| 完整离线 | **15582 passed、908 skipped、零失败／错误**，2441.83秒；16490项，原16388个ID零删除，新增102项；815个定向ID全过，原五个10秒编排窗口全过，1565个冻结输入未变 |

本批为 macOS ARM64／Python3.12 的本地验证；没有调用真实模型、远程业务、Docker、Temporal Service 或远端 CI。原全库记录15479通过／1旧夹具失败／908跳过保持，该夹具已在基线修复；本批全量结果另记。

## 已修复的真实问题

- 原型使用 Python 相等比较 JSON，False 与0可被误判相同；直接及嵌套反例先 RED，改为 canonical 比较结果、原观察与参数，不能以错误类型输出认证通过。
- 准备资源时首个无效关闭端口导致后续已创建 owner 漏关；现在先保存全部声明，原对象独立登记，清理按严格 LIFO。晚注册资源成功清理后，更早未解决声明仍保持债务；已接管 client 关闭失败不释放更早依赖。
- 错误管理返回值中显式活动 Task／Future 原先可在报告之后继续工作；现在先发现完整可见返回图，再排空原工作或保留 pending。处理 siblings、循环、已完成 Future 的结果、字典键；未启动协程只关闭，不启动；不重发业务或管理回调。
- 最终 audit、reset 和外部 cleanup retry 的晚到资源必须继续 finalization；audit只执行一次，cleanup恢复原 control 上下文，不能漏关新的已准备资源。跨事件循环 Future 不提供正常运行兼容，但 unfinished 不能被误记为 drained，实际完成后再重试原 owner。
- N10原型仅取消人工 shield observer，不能证明引擎边界；已改取消实际 engine.drive 调用方，验证原 inflight handler、Coordinator 仍被持有、原 Action／effect observation／额度和最终 cancelled。这保留低层原有业务取消语义，不冒称高层 wait 的只读观察取消。

原行为也得到确认：普通处理器异常保留 waiting_reconciliation／unknown额度；审批在额度预留之前。检查器按原 Store 事实判断，没有修改这些语义。

所有 RED、首次 CLI N08／N09失败、早期资源／返回图修复回归及参考联测保存在 `dist/node-executor-contract-20261109/`，按实际阶段解释。预览 source-targeted 的804项发生在最终修复冻结之前，不用它代签本包；以 source-final-targeted／installed-final-targeted 为准。

## 准确私有验证包

基础源码版本仍为0.1.0a8，仅隔离构建副本使用唯一私有版本；不准备新 Alpha，不替换[原推荐组合](../../docs/current-delivery.md#原推荐组合与来源)，应用未修改／重建。

| 制品 | 准确值 |
| --- | --- |
| SDK | `0.1.0a8+ncontracts.4335e907afe20318` |
| wheel | `dist/node-executor-contract-20261109/sdk-artifacts/relf_agent-0.1.0a8+ncontracts.4335e907afe20318-py3-none-any.whl` |
| wheel SHA256 | `9613b9c10865ab487baee01448407eefe791202d0e7b4d2791f60aad51c1e6fb` |
| sdist | `dist/node-executor-contract-20261109/sdk-artifacts/relf_agent-0.1.0a8+ncontracts.4335e907afe20318.tar.gz` |
| sdist SHA256 | `328505e943389d4a95d0de1b14d9be6c0c27d5c038c101817922992ca079dfce` |
| 原产品快照 | 461文件，`6e985da201ad7f7a54397d1018c97052c65b03bb318e4ba49300dcc41c40c037` |

构建与安装离线使用已有依赖，未下载新包或读取凭据。包内文档是构建时快照，最终验收／资格以本记录和当前指南为准，不覆盖冻结制品。

## 未解决与未授予资格

单独审查实证了既有 Temporal 容量 P2：默认16槽满时，第17个真实处理器未启动，但其 child 状态仍 failed。只读的 Runtime／Parent／Child State 与原 guard／end 回调复现保存在 `known-capacity/reproduce_capacity.py`、`known-capacity/known-limitation.json`，清理后剩余任务0；这不是实际 Service 验收。本批没有调整容量或添加重试，以免破坏原独占准入和实际停止契约。后续需独立设计有界背压，不能靠调大上限或盲重发掩盖。

写幂等／unknown reconciliation、Temporal 节点扩展认证、远程／更多平台、实际业务质量和外部开发者采用仍开放。原四角色通用 checker 未在本批扩修。框架整体及完整 R01–R26／M1／企业资格不因本批关闭；不宣称对等任务优于 AgentScope／LangGraph。
