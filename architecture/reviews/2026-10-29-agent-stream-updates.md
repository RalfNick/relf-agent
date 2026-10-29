# 统一模型／工具增量流验收

日期：2026-10-29。前批高层事件订阅和 DTO 校验已本地提交为 `19dcc60`，按用户授权仅该次跳过钩子，未推送。本文记录其后工作区增量；原 a8／a7 两包及 manifest、历史失败不改写，不准备新 Alpha、推送、远端 CI 或公开发布。

本文验证成绩对应本批冻结快照。随后两项边界修复与新验证单独记录于[增量观察维护](2026-10-29-stream-observation-boundaries.md)，不覆盖本文原失败、输入或私有包。

## 本批范围

本批按用户要求接续[前批 review 的第二优先级](2026-10-29-framework-alignment.md#后续优先级)，保持 [Harness](../viewpoints/harness-runtime.md) 与 [Facade](../specs/agent-facade-session-contract.md) 的执行、取消及资源所有权边界。

- `StreamUpdatePolicy` 显式选择有界展示，固定在接受的 Release，默认 `None` 不增加 Manifest 字段或展示事件；Local 默认路径避免额外全 Run 读取，并遮蔽父调用的展示上下文。
- `StreamedModelProvider` 借用原 Provider，消费一次 `stream`；保留模型能力和续接响应类型，仅在唯一完整响应、EOF 和协议校验后交还原 Engine。文本前缀不能变成工具提案。
- `emit_tool_delta()` 只在原受管理异步工具 Attempt 中报告 JSON。Local 写入原事件日志；Temporal 固定 Activity 通过原 epoch 的 Signal 交给原 Workflow 校验和记录。展示不推进业务 revision、审批、预算或效果。
- `AgentRun.stream_updates()` 投影原游标订阅为 `model_delta`／`tool_delta`／`gap`、原响应／回执结束事实与其他 Run 事实。取消订阅只结束观察；业务取消仍由原命令处理。
- 条数、总量、单条、发布等待均有界。超限、传输失败或无效进度停用展示，原完整响应继续；慢消费者读取持久事件，不能取代执行权威。磁盘同步 I/O 不承诺硬实时截止。
- EOF 后普通迭代器关闭失败保留已完成响应与清理句柄，拒绝后续派发，显式 `retry_stream_closes()` 重试。底层 Provider／客户端保持借用；真正源取消仍传播，不通过吞掉取消来宣告完成。

入口、配置、重连与清理示例见[使用指南](../../docs/agent-stream-updates.md)和[离线示例](../../examples/stream_updates.py)。独立 Agent 可直接注入策略；共享 Agent 不覆盖宿主策略。首批为 SDK 装配，未增加内置 JSON／TOML 工厂。

## 复现与修复记录

证据在忽略目录 `dist/stream-updates-20261029/`。新增契约最初 16 项失败、Local 6 项失败、Temporal 9 项失败；分别记录 RED／GREEN。审查追加复现三处 P2：完整响应后的迭代器关闭错误抹去已知结果、非实际 AsyncIterator 接收与清理丢失、展示停用后仍逐块拆分大文本。均已修复，保留原日志；随后补齐 `aclose` 属性读取失败、冻结文本块参数、续接响应与借用所有权验证。

Temporal 回调 Scope 最初的一次“RED”与源码编辑并发，实际通过，**不计为失败复现证据**。受控恢复旧浅引用代码后复现调用方修改 Scope 的失败，再采用有限 JSON 副本固定绑定，两份记录均保留。

首轮扩大源码 **1,369 passed／2 failed**，隔离安装核心 **1,150 passed**。两处失败是新增导入 `policy_identity` 遮蔽 TemporalRuntime 原同名授权身份参数，导致自定义授权策略构造失败。修复为局部别名；原 Temporal 引擎模块 **38 passed**，另加展示启用／关闭与显式／声明身份四组合，使隔离安装覆盖此路径。首轮源码输入、日志与私有 wheel 保留在 `first-expanded/`，不作为最终全绿或发行资格。

独立只读最终复核 **92 passed**，使用 `-W error`；额外检查四种自定义授权身份组合的 Release 校验。前三项 P2 与命名遮蔽修复已核对，无剩余可操作发现；未执行 Git 或真实服务／模型验收。

## 最终验证

| 项目 | 实际结果 |
| --- | --- |
| 最终源码 84 模块 | **1,375 passed**，JUnit 99.425 秒，`-W error`，零失败／错误／跳过；65 核心模块与 19 Temporal 离线／SDK 模块 |
| 目录外隔离安装 65 模块 | **1,154 passed**，JUnit 78.115 秒，`-W error`，零失败／错误／跳过；与源码对应核心完整测试身份核对 |
| 私有验证包 | `0.1.0a8+maintenance.80c39dc6dbd338b6`；wheel SHA-256 `2b57379f2ced8e3a302539b53bd7e2eb12bd4793add4cb464ae4c7d30e6b7712`；448 个产品文件、LICENSE／NOTICE、模块／METADATA 版本、独立 venv 的 site-packages 导入与 pip check 均验证 |
| 安装测试设置 | 从私有源副本复制原样测试／断言与示例，检查目录没有 src。仅异步 starter 的 installed_wheel 资源夹具使用这份精确私有 wheel 的 Python／CLI，不另建源码包。新增示例从独立目录执行两次，原命令第二次零模型／工具调用 |
| 来源和静态检查 | 源码／测试输入哈希不变，源码与安装核心测试身份完整一致；Ruff、1,476 文件格式与 Git 空白检查通过，887 个文档相对文件链接存在。a7／a8 四份原包和两份 manifest 哈希均不变 |

最终日志、输入清单、制品与核对摘要位于 `dist/stream-updates-20261029/final/`；私有包仅用于离线安装验证，未替换原 a8 或公开发行。首轮失败和原私有包留在 `first-expanded/`。

## 恢复与证据边界

Local 测试使用真实 SQLite 文件：审批停顿、游标重连、重复审批只有一次写效果；在完整模型响应／工具回执已持久化后、采纳前注入异常，关闭重开原 Store，复用原命令及日志，不重复已接受的模型调用／业务写入。该异常注入不是本次新增的操作系统进程强杀矩阵。

Temporal 覆盖纯状态、原绑定及序号／容量校验、模拟 Signal、实际 SDK 活动注册／Signal handler 和 Workflow 沙箱准备。新功能的真实 Temporal Service／History 重放及 Worker 崩溃窗口没有在本批运行，仍须独立验收；不借旧 S2／指纹或 a8 成绩放行。

本批不提供 token 断点续传、自动 reasoning／工具参数增量、stdout 截获、逐记录 Workflow、服务长连接、多模态、模型质量或平台矩阵资格。`authoritative=True` 只表示原权威已记录对应事实，可能是未采纳响应或未知效果，不等于业务成功或所有远端 handler 停止。完整 R22、R09、M1 与框架对等质量保持开放。
