# 当前本地交付

更新：2026-11-09。本页是当前 SDK／资料助手私有候选的唯一入口。下方推荐组合保持 2026-11-01 的准确候选，后续维护与能力增量按日期小节独立验证，原推荐包不含这些增量。此前源码 `e94c57c` 已使用 RalfNick 合入并推送 main，当时两个所选提交 CI 运行数核对为 0；包仍按本地文件交付，没有创建 Release。其后 `1c5bd47` 及必要祖先已按授权推送至 `codex/callable-preview-fixes`，保留 `[skip ci]`，当时核验 CI 运行数为0；未合入 main 或上传制品。其后 `e317a48` 已按授权推送同一开发分支并保留 `[skip ci]`，核验 CI 运行数为0；main、官网及原制品保持。接入边界维护源码其后已随 `8244e38` 按授权推送同一开发分支，保留 `[skip ci]`，未触发远端 CI；该维护验证包仍仅本地。Temporal 节点源码已按后续授权随 `5e2b57e` 推送同一开发分支，保留 `[skip ci]`，当时核验 CI 运行数为0；原验证包未上传。2026-11-09 节点扩展检查增量仅本地开发，不推送或公开发布。

## 2026-11-09 节点扩展检查

新增显式 `node-executor/core` N01–N10、独立 SQLite 参考与可编辑组件示例，复用原 AdapterContractSuite／LocalEngine。默认检查仍不运行 fixture 或访问服务；CLI／SDK 明确选定才执行，缺少控制能力保留未验证。原四角色摘要、执行权威与制品保持。使用与限制见[节点扩展检查](node-adapter-contracts.md)；本批源码／目录外准确安装各815项、仅运行依赖14条检查已通过；完整源码回归 **15582 passed、908 skipped，零失败／错误**。验证包为 `0.1.0a8+ncontracts.4335e907afe20318`，461个产品文件，准确制品和原失败见[本批验收](../architecture/reviews/2026-11-09-node-executor-contract.md)。不授予完整 R25、写效果、Temporal 或真实业务质量资格。

## 2026-11-05 Temporal 受管理节点

基于 `8244e38` 的当前源码增加无会话的 Temporal `GraphNode(executor=...)`，复用原 NodeExecutorRegistry、Parent History 和 Native 单 Tool 子 Run；支持静态串行／有界并行、显式 Agent 混合图及原 Team／Dynamic 嵌套。默认 identity 与 SDK／Temporal Profile 的工厂装配沿原生命周期；不增加执行权威，完整边界和显式 Service 示例见[使用指南](temporal-managed-nodes.md)。

源码与准确隔离 wheel 的真实 Service／恢复矩阵各13项、同组离线回归各690项通过；原完整轮15479通过／1项旧夹具失败／908条件跳过；该夹具修复后原模块源码／安装各8项通过，459产品未改，未重新执行整轮。验证 SDK 为 `0.1.0a8+tnodes.3675891f64d0664f`，459个产品文件；准确制品、历史失败和所选旧 History 兼容见[本批验收](../architecture/reviews/2026-11-05-temporal-managed-nodes.md)。这些不授予新的平台／模型质量资格。Session／Turn／native history、Coding composition、部署准入及 parent completion 组合继续拒绝。旧 Coding History 固定纯实现指纹，须保留原包／匹配 Worker，不保证使用新 Worker 透明回放。

下方原推荐 SDK／应用、Local 节点验证包、接入边界验证包及原 a8 全部保持原字节和原验收范围，均不包含本批节点能力。Temporal 源码其后随 `5e2b57e` 推送开发分支，原包仍未上传或公开发布；本包仅为本能力本地验证，不替换原推荐组合；不使用之前15397项或旧 Service成绩代签。

## 2026-11-05 接入边界维护

对比 AgentScope／LangChain／LangGraph 后，先修复既有 Schema、Embedding 和聊天入口的稳定性／易用性问题，保持执行权威与恢复契约，不增加新功能。范围、实际验证和准确安装来源见[维护验收](../architecture/reviews/2026-11-05-framework-boundaries.md)，剩余短板见[对比](../architecture/reviews/2026-11-05-framework-alignment.md)；普通工具与节点的引用／升级约束见[Schema 指南](schema-validation.md)。原推荐组合与节点验证包均保留；它们不包含本批产品修复，本轮源码完整回归15397通过／895条件跳过、准确安装1344项和运行依赖14条检查通过。验证SDK为 `0.1.0a8+boundaries.78b549d7aed371da`，仅本地验证，不替换原推荐组合；包内文档是构建时快照，最终范围以维护验收为准。

## 2026-11-04 编排崩溃测试收口

本批仅修复测试运行环境与 SQLite 连接所有权，SDK 的455个产品文件未改，原推荐组合、节点验证包和历史制品保持。原五个窗口继续使用每子进程10秒，源码／准确安装相关集合各33项、旧新夹具双向20个进程和修复后完整离线回归 **15319 passed、895 skipped，零失败／错误** 通过，原测试ID全部保留。宿主睡眠与FD增长有直接记录，历史子进程的精确停点／唯一原因仍不作推断。范围、阶段证据和已知限制见[本批验收](../architecture/reviews/2026-11-04-orchestration-crash-timeouts.md)。仅本地提交，不推送、触发远端CI或公开发布。

## 2026-11-04 本地 Workflow 能力增量

新增 Local 通用受管理异步节点，声明、默认实现和替换配置见[指南](managed-async-nodes.md)。准确验证包为 `relf-agent==0.1.0a8+nodes2.636723b3b3d32c60`，对应 `e75c756` 之后本批源码快照；455 个产品文件一致，wheel／sdist 的完整 SHA、安装和恢复证据见[本批验收](../architecture/reviews/2026-11-04-managed-async-nodes.md)。构建时源码尚未提交，最终本地提交包含同一产品快照和后续文档收尾，原构建记录保留。

最终源码／准确安装各 **1003 项**通过；README 长描述同时修正四个基线既存相对链接，首验证包另行保留。首次全量预检的 6 项链接失败已闭环，另 2 项旧崩溃窗口超时在原 10 秒期限下三轮复验通过，但整轮时序尚未验证为稳定，这是该首轮的历史结果；后续修复和整轮复验见本页上方专项，原失败保持。

本批支持 Local 串行／有界并行图及原 Team／Dynamic 的嵌套图，复用原 Tool Action 协议。Temporal 不支持 executor 图；真实服务、模型质量和新平台资格均未由此次离线验证授予。验证包仅供本能力本地试用，不替换下方 SDK／资料助手推荐组合；原推荐包不含这些新节点。源码 `1c5bd47` 已按后续授权推送上述开发分支；验证包仍仅本地，未触发远端 CI、部署官网或公开发布。原 Alpha／其他制品均保留。

## 2026-11-03 本地能力增量

按用户新授权补齐固定 HTTP GET 查询／参数映射，以及既有增量策略的 JSON／TOML 配置；相关源码与准确安装各440项通过，独立本地验证包及边界见[本批验收](../architecture/reviews/2026-11-03-foundation-gaps.md)。本批源码、测试与文档已随 `1c5bd47` 推送开发分支；本地验证包未替换下方原推荐候选，也未部署官网或公开发布。原包不含这两项新增配置能力。

## 原推荐组合与来源

| 项目 | 当前固定值 |
| --- | --- |
| 实现提交 | `80de9bdc2188d27067c7acd752f5f5a796cbea48`，本地 `codex/callable-preview-fixes` 分支 |
| SDK | `0.1.0a8+maintenance.a97223496646bac0`；发行名 relf-agent，导入 relf_agent，CLI relf |
| SDK wheel | `dist/callable-preview-fixes-20261101/sdk-artifacts/relf_agent-0.1.0a8+maintenance.a97223496646bac0-py3-none-any.whl` |
| SDK wheel SHA256 | `5cfbfec568a26445efd8a9c6009adc60660f320fcf875a747ddfea37e370363b` |
| SDK sdist | `dist/callable-preview-fixes-20261101/sdk-artifacts/relf_agent-0.1.0a8+maintenance.a97223496646bac0.tar.gz` |
| SDK sdist SHA256 | `b88d0b054b721f6f8e3eadbf57dcf7c20ddd47ee0e651aaf639299dc80d99a92` |
| 资料助手 | `0.1.0+local.3d98685c70e5`，精确依赖上述 SDK；模块 local_documents，CLI relf-docs |
| 应用 wheel | `dist/callable-preview-fixes-20261101/application-artifacts/relf_local_documents_example-0.1.0+local.3d98685c70e5-py3-none-any.whl` |
| 应用 wheel SHA256 | `e7a8d3488590ef92d96d96e7e440b763dae099e08d22072b177069b50add4fbf` |
| 应用 sdist | `dist/callable-preview-fixes-20261101/application-artifacts/relf_local_documents_example-0.1.0+local.3d98685c70e5.tar.gz` |
| 应用 sdist SHA256 | `10f48dc1394136be272e7eefe17f72fafcbc22690e2be721c205ce1656c55bb7` |

相对前候选 `.f3da3f48e894e745`，451个SDK产品文件只有tools.py改变；应用只修复人工呈现并固定依赖。源码基版本仍是0.1.0a8／0.1.0，隔离构建副本同时设置发行与模块私有版本。制品内文档是准确构建提交快照，最终验收以本页和[本批记录](../architecture/reviews/2026-11-01-callable-preview-fixes.md)为准；文档收尾不重建已冻结包。

## 安装与依赖

先核对本页SHA，将文件名替换为收到的实际绝对路径，再从新目录执行：

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install /ABS/relf_agent-0.1.0a8+maintenance.a97223496646bac0-py3-none-any.whl
python -m pip check
relf --version
relf init my-agent
```

资料助手的三份准确材料、完整哈希核对与启动步骤见[应用交付](local-documents-assistant.md)。默认SDK仅需原httpx／jsonschema，不需Temporal、Redis、Docker或模型密钥；实际模型由使用者显式配置。没有新增依赖或公共执行接口。

## 冻结支持范围

| 范围 | 本批已验证与边界 |
| --- | --- |
| Callable | 普通函数／方法、partial与子类、Python／标准property的__call__、类的有效metaclass-call/new/init继承入口静态固定；已捕获原生函数保留原绑定，不按类名重取。未知描述符、partial.func遮蔽和无原身份元数据的method-wrapper提前明确拒绝 |
| 身份与恢复 | 原持久工具Manifest／implementation_digest不变；getter返回的任意辅助对象、闭包／默认参数／状态／外部依赖仍需显式version/config；不递归证明任意Python执行图 |
| 审批呈现 | 人工stdout/stderr使终端控制与格式字符可见；预览明确标注转义显示。原始正文、SHA、Action／摘要、JSON字段值和保存回执不变 |
| 原执行链路 | 沿用Agent／Session／Workflow、预算／审批／unknown核验和Local／Temporal各自权威；没有增加后端、节点或执行模式 |
| 官网 | 本地源码的当前交付链接指向main；教程代码／其他repo链接、元数据日期和源哈希仍固定300c62c。仅本地构建，没有部署或线上核验；main链接展示公开main而非本地未推送的新候选 |
| 验收资格 | 本批macOS ARM64／Python3.12；原模型、平台和Service成绩保持原制品范围，不授予新平台、真实模型或企业完整资格 |

具体允许／拒绝形态见[扩展指南](extending.md)。原应用任务仍须保留原代码、配置、数据库和目录恢复；本批不提供自动任务迁移。直接代码变更被拒绝时保留原证据与资源，恢复原实现后处理原Run并重试原实例关闭，已发生的外部效果不会回滚。

## 本批验收

- 源码与准确SDK＋应用安装各 **1407 passed**，零失败／错误／跳过，同一测试ID；原1320节点和1项排除保持，分别306.35／304.87秒。矩阵在独立进程／临时数据库中执行，不是全SDK或平台验收。
- 新增59项Callable与28项终端反例；集中审查的已捕获原生方法误判以4个RED闭环，相关240项转绿。原失败与环境失败保留。
- 独立运行依赖环境无pytest／Temporal，24条命令通过；准确SDK sdist中的应用重新构建／安装成功；聊天双次启动关闭无Run或模型请求；所选前SDK↔新SDK默认业务审批／重启／去重双向通过，每例一次效果。
- 官网31项测试、14对双语源核对、Astro零错误／警告、本地32页构建与1985链接／资源核对通过；固定教程离线命令验证通过。没有远端检查、部署或线上资格。
- 21份历史制品和原始记录保持，原未跟踪审查文件没有修改或代为提交。

## 已关闭与待验证

本批五项问题已收口，不自动增加开发队列。新候选没有真实模型调用或新Service／平台验收。所选真实模型任务质量、其他平台／解释器、其余Temporal故障窗口、独立采用、公开包／索引安装、完整M1／R01–R26和对等比较仍独立待验证。未闭合斜杠命令引号退出聊天的问题已在2026-11-05维护源码修复；原推荐应用包不含该补丁。

<a id="当前执行目标2026-11-01-本地示例-agent"></a>
<a id="当前执行目标2026-10-30-再审后"></a>

## 历史交付与目标

资料助手首版及前次四项P2／源码包修复已经完成，原 `.f3da3f48e894e745`／应用 `0.1.0+local.ddcf607b0929` 保持原SHA与[验收](../architecture/reviews/2026-11-01-stability-review-fixes.md)。更早SDK／应用、Alpha、S2和函数指纹记录按原范围保留。独立业务采用继续后续，见[接入流程](independent-onboarding.md)。新源码推送、CI、发布或官网部署均需另外明确授权。
