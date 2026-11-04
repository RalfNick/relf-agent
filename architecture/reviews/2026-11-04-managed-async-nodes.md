# Local Workflow 通用受管理异步节点验收

日期：2026-11-04。用户授权补齐 Workflow 的有限异步节点，保持原执行权威与恢复契约；只本地提交，单次跳过 Git 钩子，不推送、触发远端 CI 或公开发布。设计与实现计划开始于 2026-11-03，证据目录沿用该日期。原 a8／历史制品、失败及用户既有审查文件全部保留。

## 实现范围

- `NodeExecutor` 是结构化异步端口，无须继承内置基类；可选 `NodeReconciler` 按原 `EffectObservation` 提交核验证据。`NodeExecutorSpec` 明确版本、效果类型、Schema、审批及额度成本。
- `GraphNode(executor=..., input=..., config=...)` 支持有限 JSON 输入和递归 `InputMap`，编译到原 Tool v2／并行 v3；不增加 IR 版本、Action 种类、SQL Schema、调度器或执行权威。原 v1–v3 未选择新能力时规范字节保持。
- Registry 借用第三方组件；原组件工厂／BuildContext 管理 owned／borrowed 客户端。默认 `workflow_executors/identity` 可通过 JSON／TOML 同步／异步装配，不需要模型或新增依赖。
- 私有别名只在准确 plan 节点、注册及固定 Manifest 匹配时执行。编译出的原 ToolNode 可经 `from_plan` 重建；Agent 工具和 binding tool_set 不得到该别名，普通工具仍走原可替换 ToolExecutor。
- 调用前后及结果接收时固定组件身份和直接方法入口；输出 Schema 在效果事实持久化后检查。取消观察不回滚业务操作，实际处理器退出与关闭重试继续使用原生命周期规则。

支持 Local 串行、有界并行和原 Team／Dynamic 中的嵌套图。Temporal 在请求、递归定义、Worker 及 Profile 边界拒绝此类图／Local 组件；本批不交付 Temporal 节点执行。循环、通用节点族、reducer、逐记录流式 Workflow、沙箱及新的真实服务质量不在本批。

完整 API、配置、所有权和示例见[使用指南](../../docs/managed-async-nodes.md)，离线示例见[managed_async_nodes.py](../../examples/managed_async_nodes.py)。

## 测试和故障窗口

定向覆盖声明／旧字节、第三方 async callable、默认和替换工厂、混合图／绑定／嵌套、审批／授权／预算、四类效果、null 证据、私有名称隔离、实现漂移及输出 Schema。真实子进程分别在 intent 提交、外部业务提交、receipt_received 提交、Action 完成但节点未完成四个窗口退出；恢复检查原 Run／Action／effect_key、调用次数、额度和结果。串行及并行 frame 都复用原恢复机制。

取消测试覆盖观察者取消后继续驱动、处理器吞掉取消、实际工作未结束时关闭拒绝、原实例关闭重试和并行失败排空。不能把异步方法被取消理解为任意第三方外部操作被撤销。

一次独立审查发现一个 P2：私有适配器对象固定仍不足以防止 execute／reconcile 方法或 Registry 所有者被替换。补充方法入口、原地代码及所有者 pin，并把适配器直接实现纳入所选 Manifest；9 个有效反例 RED→GREEN。审批命令仍可保存原摘要回执，在实际派发前拒绝漂移；恢复原实现后可使用原回执继续。初始错误地要求 approve 拒绝的测试及失败日志也保留，未修改原审批语义。闭包、客户端内部状态及外部依赖仍由集成方版本／identity 明确固定，不声称递归保护任意 Python 执行图。

## 准确验证制品

源码基线：`e75c7561bb14eb54e3f80d32e6dcbc59cd86143d`。构建时为基线加本批工作区，`source_is_uncommitted=true` 保留真实来源；本地提交不重写构建历史。基版本保持 `0.1.0a8`，仅隔离构建副本同时修改发行与模块私有版本。制品内文档保留构建时快照，本页、机器记录及状态文档是验证后的收尾；不重建已冻结包，455 个产品与最终源码分别核对。

- 版本：`0.1.0a8+nodes2.636723b3b3d32c60`。
- 产品清单：455 个 `.py`／`.json`；摘要 `e749eb31046f475f23c933684347f38a5a46f923db38d5c9f0ed4bb8f18cdb73`。
- 最终制品：`dist/managed-async-nodes-20261103/final/sdk-artifacts/`；原始日志及首包：`dist/managed-async-nodes-20261103/`（均为本机忽略目录，不作为远端可下载入口）。

| 制品 | SHA256 |
| --- | --- |
| `relf_agent-0.1.0a8+nodes2.636723b3b3d32c60-py3-none-any.whl` | `fe07c8015efbd44284eac0909d6b30855cb67f4a79f6c5c4d5ea57230a46b6fa` |
| `relf_agent-0.1.0a8+nodes2.636723b3b3d32c60.tar.gz` | `dd293a2f9a7ae111122fc3d9627eed29d0f27b8b99959a5ca492b78f3d8b9211` |

## 验证结果

- 57 个相关模块加 6 项 README 契约：源码 **1003 passed**（243.16 秒），准确 wheel 目录外安装 **1003 passed**（219.64 秒），相同测试 ID，零失败／错误／跳过。新增 153 项覆盖本能力，包含 9 项审查修复反例。安装测试文件未改；对需要 checkout 的旧构建夹具复用准确 wheel，README 检查读取实际 wheel 的 METADATA 长描述。
- 首次全量离线源码回归：**15303 passed、895 skipped、8 failed**，2286.70 秒。6 项 README 契约是基线既存的四个相对链接，独立 RED→GREEN 后纳入新包元数据；另 2 项旧编排崩溃窗口的 10 秒子进程超时，在原期限下单独串行三轮均为 5/5 通过，未改产品或期限。其整轮／宿主时序根因未确认，**不声明全库已通过**；本批定向矩阵不抹去原失败。跳过原因及逐轮结果见机器记录。
- 最小运行依赖环境无 pytest／Temporal，wheel 安装、CLI／starter、默认节点及 sdist 重建安装共 **10 条命令**通过；重建后 455 个产品与准确 wheel 一致。
- 前一 `.foundation.4d5f21d82d5d96bd` SDK 与新包双向执行 Agent／v1／v2／v3 共 **8 例、24 个进程**；旧 SDK 拒绝新节点另 2 个进程。总共 26 个进程，4 次应有业务 POST，每例一次效果，未使用原证据数据库。
- 已安装示例从 checkout 外执行 **5 个进程**：首次／重复提交、审批前暂停／冷进程续接、默认临时目录。相同 Run／Action／effect_key／回执和一次业务效果均核对。
- Ruff、格式及 Git 空白检查通过；原 **292 个制品**、本批首验证包的 wheel／sdist 与用户既有审查文件 SHA 保持。直接节点恢复／取消测试拥有的 28 个子进程均已结束，未遗留实际外部服务。

最终准确哈希、测试计数和限制见[机器记录](../../evals/results/relf-managed-async-nodes-20261104.json)。验证包括相同测试 ID 的源码／目录外准确安装、运行依赖安装、sdist 重建、跨版本恢复及已安装示例；不借用历史包的平台或真实服务资格。

首包 `0.1.0a8+nodes.e749eb31046f475f` 的源码／安装各 997 项、10 条运行依赖命令、26 个兼容进程及 5 个示例进程仍保持原记录。README 长描述修复影响元数据，因此另冻上述 `.nodes2` 唯一版本；455 个产品代码完全相同，未覆盖首包或借用其安装结果。最终矩阵、运行依赖、兼容和示例均按新包独立串行执行。

## 保留的失败与边界

原 Registry／编译／Local／配置反例 RED、错误测试路径、首次适配器审查测试以及修正后的有效 RED 全部保留，不覆盖日志。首次隔离矩阵 992 项通过、5 项夹具 setup 错误：旧 starter 夹具要求从 checkout 构建，但目录外环境无 build／源码项目。复验仅在验证插件中让该夹具复用本次准确 wheel，测试文件保持不变；独立 sdist 重建另行验证构建能力，不将夹具错误改写为产品失败或默默跳过。

本批仅 macOS ARM64／Python 3.12 离线证据；真实 Temporal Service、模型质量、新 Linux／原生 AMD64／其他 Python、独立采用和对等框架评测继续分别验收。R08 仅新增 Local 子集，完整 R01–R26、企业目标和新的公开发行均未据此完成。

## 后续测试专项（2026-11-04）

原八项失败与本批制品不改写。旧编排10秒窗口的宿主／连接资源修复及完整离线复验见[后续记录](2026-11-04-orchestration-crash-timeouts.md)；SDK产品字节不变，该后续验收不替换历史 sdist 中的测试快照，也不扩大平台或真实服务范围。
