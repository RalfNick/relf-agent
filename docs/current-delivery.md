# 当前本地交付

更新：2026-11-09。本页区分推荐组合、已推源码和各批有限验证包。先选择下表中的准确快照，再使用对应指南；历史验收与平台、模型或服务资格不在快照之间自动继承。

## 先选择交付快照

| 使用目标 | 准确快照 | 范围与选择 |
| --- | --- | --- |
| 运行当前推荐 SDK／资料助手 | SDK `0.1.0a8+maintenance.a97223496646bac0` ＋应用 `0.1.0+local.3d98685c70e5` | 保持 2026-11-01 原组合；[精确 SHA 与安装](#原推荐组合与来源)，不包含其后各批增量 |
| 阅读最新已推开发源码 | `4bb46fe`，`codex/callable-preview-fixes` | 已推送、保留 `[skip ci]`，当时 CI 核验为0；包含截至节点扩展检查的已推增量，后续容量／诊断与节点／检索维护仅本地交付；推送不等于上传安装包 |
| 阅读公开 main | `e94c57c` | 与开发分支分开；不能据 main 链接推导最新开发能力已合入 |
| 检查节点扩展接入 | `0.1.0a8+ncontracts.4335e907afe20318` | [有限 Local 读取型检查](node-adapter-contracts.md)，仅本地验证，不替换推荐组合 |
| 验证容量背压／关闭诊断 | `0.1.0a8+capacity.c5a29d8fa601a9ec`，基线 `4bb46fe` | 464产品私有验证包；源码／准确安装各884项及各5项Service、完整离线15685通过／913条件跳过；不替换推荐组合 |
| 验证本轮节点／检索边界 | `0.1.0a8+guards.34d5fe53e3fe66ef`，基线 `ec23ae5` | 464产品私有验证包；源码／准确安装同603项通过，完整离线15718通过／913条件跳过；不替换推荐组合 |
| 核对官网／公开发行 | 原官网固定教程、原 Alpha 和公开安装记录 | 本轮不部署官网、上传制品或公开发布；与上述本地验证分开 |

## 2026-11-09 节点／检索后续维护（有限验收完成）

基于已本地提交、尚未推送的 `ec23ae5`，本轮只修复 Local 节点公共注册端口漂移和异步向量检索跨 TTL 返回问题。准确候选固定464产品／1580输入，源码与目录外准确安装同33模块、603个测试ID全部通过、零跳过，JUnit分别107.505／144.493秒；同一冻结输入的完整离线回归自然退出0，**15718通过／913条件跳过、零失败／错误**，共16631项，JUnit2347.255秒、runner2351.459秒。完整成绩来自本轮实际运行，不以定向或上批成绩代签。指南见[受管理节点](managed-async-nodes.md)与[检索](hybrid-retrieval.md)。

最终审计确认原16598个测试ID及其15685通过／913跳过状态保持，新增33项全部通过，本批603项在完整轮中全部通过；原五个10秒恢复窗口及两项连接关闭检查通过。464产品／1580输入、308份原包和封存历史证据SHA保持，原pytest／guard进程组已退出。跳过项不授予真实服务资格，推荐组合、平台和模型质量范围保持。

| 本轮私有制品 | 准确值 |
| --- | --- |
| SDK | `0.1.0a8+guards.34d5fe53e3fe66ef`；464产品，1580冻结输入 |
| wheel | `dist/framework-maintenance-20261109/sdk-artifacts/relf_agent-0.1.0a8+guards.34d5fe53e3fe66ef-py3-none-any.whl` |
| wheel SHA256 | `bce93dd4312ffb61f182016add8b6628d7ba7ccbac261f8acdb2e52761fafe84` |
| sdist | `dist/framework-maintenance-20261109/sdk-artifacts/relf_agent-0.1.0a8+guards.34d5fe53e3fe66ef.tar.gz` |
| sdist SHA256 | `760d9bd723a806b1a8ac3f2f354918586e175f54028e7ef82c55a46486c9b8f6` |

首次安装回归为600通过／3个旧RAG starter构建夹具错误，原XML保留。只在隔离测试环境补齐显式 `build`／`setuptools`／`pyproject_hooks` 和冻结构建输入后，同603项通过；未给产品增加这些开发依赖。安装检查无checkout `pythonpath`，SDK继续从该虚拟环境的site-packages导入；夹具重建包的464产品亦一致。独立的仅运行依赖环境10条检查通过，sdist重建464产品字节一致。所选普通Local／Temporal、节点与Knowledge身份及8个catalog摘要保持；仅为所选元数据兼容，不授予任意旧History、Session、Coding／部署或私有辅助函数漂移兼容。

Local六公共入口固定沿用原注册边界；本轮已保存回执的await漂移场景中Run保持原 `failed/definition_mismatch`，该回执可在原恢复路径采纳／结算，不重派发或重开失败终态。检索只复核最终采用结果的已知TTL，不新增来源I/O或自动刷新。准确分层证据见[本轮记录](../architecture/reviews/2026-11-09-framework-maintenance.md)和[机器记录](../evals/results/relf-framework-maintenance-20261109.json)。原308份包、所有历史失败、推荐组合及上批容量包保留，不增加新的平台／模型／服务或完整R项资格。仅本地提交，以Git记录为准，不推送或公开发布；包内文档是冻结时快照，最终状态以本页及本轮记录为准。

## 2026-11-09 容量背压／关闭诊断维护（有限验收完成）

本轮只处理原 Temporal 节点 owner 饱和后的未启动拒绝、兼容的只读关闭诊断和本页入口整理。新默认节点 owner 的未 claim 容量证明交原 Native History 有界 timer，保持同 Action／attempt／effect key 与预算；关闭诊断只读投影，原 report、取消及 owned/borrowed 责任保持。准确源码／目录外安装各46模块 **884 passed、0 skipped**，最终源码／安装真实 Service 矩阵同5个ID各 **5/5通过**，分别95.17／89.25秒。仅运行依赖16条检查通过，sdist重建后464产品逐字节相同；冻结源码完整离线 **15685 passed、913 skipped，零失败／错误**，共16598项，JUnit2438.285秒；本轮有限维护按这些分层证据验收。

| 本轮私有制品 | 准确值 |
| --- | --- |
| SDK | `0.1.0a8+capacity.c5a29d8fa601a9ec`；464产品，1578冻结输入 |
| wheel | `dist/temporal-capacity-close-20261109/sdk-artifacts/relf_agent-0.1.0a8+capacity.c5a29d8fa601a9ec-py3-none-any.whl` |
| wheel SHA256 | `5536d856fa3b91bbb12c85a094ce6e928077ca4c4a3bf1d01b7c747d5b4ad918` |
| sdist | `dist/temporal-capacity-close-20261109/sdk-artifacts/relf_agent-0.1.0a8+capacity.c5a29d8fa601a9ec.tar.gz` |
| sdist SHA256 | `506ba759b648dbb3c77e3f8304c4a7fc3a77111608007d1e70202c5c3afe9d2d` |

源码／安装Service覆盖单图17节点、两个 Run 共用16＋1槽、History Worker 冷重启、容量等待中取消及 ACK 拖延后的关闭重试；冷重启保留独立 Activity Worker 和真实处理器，不代签物理执行 Worker 全冷恢复。原10秒Activity／20秒Worker ready／30秒就绪／120秒用例期限保持；完整轮中旧五个编排崩溃测试另有各10秒子进程门槛，二者分别核对。

所选兼容检查确认七个旧catalog、普通Temporal release、显式原节点owner release、原Context execute／wait／aclose及通知描述相同；新默认节点owner身份变化符合预期。这仅为所选元数据兼容，不授予任意旧History、Coding或部署指纹迁移资格。完整轮首轮因默认沙箱阻断本机端口而主动中止，原部分结果保留；同一命令和门禁在允许本机端口的上下文完整复验已自然结束、退出0；原16490个测试ID全部保留，本批884个定向ID及原五个10秒崩溃窗口全过，464产品和1578输入未变。913项条件跳过包含本次5个Service用例，其真实Service资格来自上述源码／准确安装各5/5独立运行，不由跳过授予。协议、原失败和分层结果见[本轮验收](../architecture/reviews/2026-11-09-temporal-capacity-close.md)及[机器记录](../evals/results/relf-temporal-capacity-close-20261109.json)，使用见[Temporal 节点](temporal-managed-nodes.md)与[关闭诊断](close-diagnostics.md)。

原推荐组合、Alpha、所有历史制品与失败记录保留。新默认节点发布及所选 Coding／部署指纹变化，旧任务须原包／匹配 Worker；不外推任意旧 History、平台、模型或企业资格。本地提交以Git记录为准，单次跳过钩子；未推送或公开发布。包内文档是冻结时快照，最终验收以本页和本轮记录为准。

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

## 源码推送历史

更新：2026-11-09。本页是当前 SDK／资料助手私有候选的唯一入口。下方推荐组合保持 2026-11-01 的准确候选，后续维护与能力增量按日期小节独立验证，原推荐包不含这些增量。此前源码 `e94c57c` 已使用 RalfNick 合入并推送 main，当时两个所选提交 CI 运行数核对为 0；包仍按本地文件交付，没有创建 Release。其后 `1c5bd47` 及必要祖先已按授权推送至 `codex/callable-preview-fixes`，保留 `[skip ci]`，当时核验 CI 运行数为0；未合入 main 或上传制品。其后 `e317a48` 已按授权推送同一开发分支并保留 `[skip ci]`，核验 CI 运行数为0；main、官网及原制品保持。接入边界维护源码其后已随 `8244e38` 按授权推送同一开发分支，保留 `[skip ci]`，未触发远端 CI；该维护验证包仍仅本地。Temporal 节点源码已按后续授权随 `5e2b57e` 推送同一开发分支，保留 `[skip ci]`，当时核验 CI 运行数为0；原验证包未上传。节点扩展检查源码其后随 `4bb46fe` 按授权推送同一开发分支，保留 `[skip ci]`，当时核验 CI 运行数为0；原验证包没有上传。下方各批“仅本地”描述保留冻结时状态，本轮容量背压／关闭诊断维护另行本地验证，不推送或公开发布。

## 历史交付与目标

资料助手首版及前次四项P2／源码包修复已经完成，原 `.f3da3f48e894e745`／应用 `0.1.0+local.ddcf607b0929` 保持原SHA与[验收](../architecture/reviews/2026-11-01-stability-review-fixes.md)。更早SDK／应用、Alpha、S2和函数指纹记录按原范围保留。独立业务采用继续后续，见[接入流程](independent-onboarding.md)。新源码推送、CI、发布或官网部署均需另外明确授权。
