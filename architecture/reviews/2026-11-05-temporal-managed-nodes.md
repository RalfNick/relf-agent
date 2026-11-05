# Temporal 受管理节点验收

日期：2026-11-05。源码基线 `8244e38642913596fbdeff8059407194466d063a`，本批只本地提交，不推送、远端 CI 或公开发布。原 a8、推荐组合与历史记录保持。

## 交付范围

Temporal 显式注册 `workflow_executors` 后，支持无会话的 `GraphNode(executor=...)`：静态串行、有界并行、显式 Agent 混合图及原 Team／Dynamic 嵌套。复用原 NodeExecutorRegistry、结构化异步组件、完整 JSON 输入、独立 config、两级输出 Schema、SDK／JSON／TOML 工厂和默认 identity；无模型节点可以不配置 Provider。

原 Parent History 管理依赖、子 Run 和真实 cost 的额度托管；原 Native Run 将 executor 降低为单个私有 ToolAction，复用审批、授权、Journal、未知效果、ACK 与实际处理器停止。不增加 Workflow／Activity 名，不在 Activity 内运行 LocalEngine，不构造虚假 Agent 或增加执行权威。内部 alias 不向 Agent 工具集合开放。

使用入口见[节点指南](../../docs/temporal-managed-nodes.md)与[真实 Service 示例](../../examples/temporal_managed_nodes.py)。设计与实现计划分别见[规格](../../docs/superpowers/specs/2026-11-05-temporal-managed-nodes-design.md)和[计划](../../docs/superpowers/plans/2026-11-05-temporal-managed-nodes.md)。

## 本批结果

| 验证 | 实际范围和结果 |
| --- | --- |
| 源码定向回归 | 32模块 **690 passed，0 skipped**，`-W error`，48.07秒 |
| 准确 wheel 安装 | 同690个测试ID **690 passed，0 skipped**，46.54秒；从仓库外 site-packages 导入，无 checkout/src 或 PYTHONPATH 注入 |
| 源码真实 Service | 首项通过后运行其余12项，共 **13 passed，0 skipped**；原120秒个案／30秒观察／10秒 Activity 门槛不变 |
| 安装包真实 Service | 同一 wheel 的同13个测试ID **13 passed，0 skipped**；Worker、示例均使用准确安装，原 namespace 回放 |
| 实际恢复 | 审批期间 kill／重启 Worker、重复命令、PG 写后回复丢失、已收回执与实际结束后 Activity 回复前崩溃、写已提交但实际结束未知、Schema 失败保留业务效果、取消后 CloseIncomplete 与原对象重试 |
| History 回放 | 每轮53份原 Parent／Native／Registry History 在原 namespace 回放；另源码／安装包各回放所选3份2026-10-29普通无节点 History |
| 仅运行依赖 | **10条命令通过**，核心 Local smoke 不安装 pytest／Temporal；sdist 重建的459个产品与 wheel 一致 |
| 独立 review | 三次只读核对，独立78项通过；发现的宿主 allowed_tools 缺口已 RED 后修复，最终未发现新增可确认 P1／P2 |
| 完整源码 | 原完整轮 **15479 passed、1 failed、908 skipped**，2794.69秒；16388项，原16292个测试ID零删除，新增96项。唯一旧夹具缺项修复后，原模块源码／安装各8项通过；没有再次全库运行或改写原失败。整轮期间1557输入未变，其后仅补1份测试夹具，459产品不变；原五个10秒编排崩溃窗口全过 |
| 完整性 | 基线300个制品保持原 SHA；受保护未跟踪审查文件未改，未调整持久 Git hooks |

真实服务使用原缓存 Temporal CLI 1.9.1／Server 1.32.0、SDK 1.34.0，本机 macOS ARM64／Python 3.12。独立 PostgreSQL 16 容器限1 CPU、512 MiB，仅绑定回环；没有 time-skipping、真实模型或远端业务调用。节点-only 用例模型调用0，混合图只调用显式声明的1个脚本 Provider，不能据此证明真实模型质量。

每个写效果场景都核对原 PG 业务表实际写入1次，未知效果恢复只调用 reconcile。`commit-crash` 缺少实际停止证明时，预期结果是保留未知效果、预算和原工作责任，阻止再次 execute；**该用例通过不代表该业务 Run 成功或任意外部操作恰好一次。** 测试清理会显式终止自有未结束 History，这也不构成业务停止证据。

## 修复与原失败

- 确定性测试闭环父子身份、私有 alias 越权、宿主 allowed_tools、原 cost=0／1／9、输入／输出、预算与取消。延后 ACK 的遗漏先 RED，再使其继续阻止节点完成；不重新 execute。
- 真实首项暴露父 Workflow 激活阶段动态导入。补原父预加载，并将两个纯节点模块纳入原 SDK 的纯规则白名单；真实 SDK importer 对 Native／Parent／Session 三个入口通过，没有关闭沙箱或警告。
- 后续首项在派发前被 `definition_mismatch` 拒绝，业务 execute=0。先修复 base Manifest／完整 orchestration release 变体，再用实际 History 定位原元组与 JSON 数组差异。仅规范化 Worker 原固定发布，再完整匹配；伪造发布、Scope、参数和父子身份仍拒绝。补 full release 的 JSON wire RED／GREEN，未信任调用方替代注册。
- 首轮其余12项为7通过／5失败：三项夹具比较子进程就绪的原生元组与 JSON 列表，一项在示例已关闭 Worker 后查询在线状态，一项把 reconcile 命令 accepted 当成父级异步采纳完成。分别使用规范 JSON、原 Service History 只读发现和原30秒状态观察修复；没有调整期限或产品取消语义。
- 早期离线探针的路径／Scope／缺少父 release_digest、协议字段类型和 importer host-cache 误用，与实际产品 RED 分开保留。历史回放探针首轮重复收集 pytest `current` 符号链接导致数量断言失败，原 History 已回放；排除别名后核对3份唯一原记录，不修改 History。
- 完整轮唯一失败是旧 ACK 关闭测试将真实方法绑定到缺少 `_manifest` 的简化 Runtime。独立探针捕获 `AttributeError`、Journal 调用0，静态审查确认真实 Runtime 始终初始化该字段。仅在该夹具补原固定 Manifest，保留全部 SDK／关闭／一次 ACK 断言；源码与目录外准确安装原模块各8项通过，产品459文件未变。原完整轮失败 XML 保持，未再次执行全库，不将定向复验改写成整轮全绿。

原始证据分别保存在忽略目录 `dist/temporal-managed-nodes-20261105/` 和 `dist/temporal-workflow-nodes-20261105/service/`，不覆盖任一失败 XML、日志或 SQLite 数据。[机器验收记录](../../evals/results/relf-temporal-managed-nodes-20261105.json)保存准确来源与分项结果。服务汇总为 `source-acceptance-summary.json`／`installed-acceptance-summary.json`；最终自有资源缺失核验为 `owned-resource-verification.json`。PG stop／rm 均退出0，原清理脚本另有 stdout 标识相等判断为 false 的记录，原字段保持，用独立只读核验补证。用户容器及 Docker Desktop 未停止。

## 准确本地验证制品

不是新的公开 Alpha，不替换[原推荐 SDK／资料助手组合](../../docs/current-delivery.md#原推荐组合与来源)。基础源码版本仍为0.1.0a8，构建副本使用唯一私有版本；应用没有改动或重建。

| 制品 | 准确值 |
| --- | --- |
| SDK | `0.1.0a8+tnodes.3675891f64d0664f` |
| wheel | `dist/temporal-managed-nodes-20261105/sdk-artifacts/relf_agent-0.1.0a8+tnodes.3675891f64d0664f-py3-none-any.whl` |
| wheel SHA256 | `c0018a3359be99a285f326307bc5a50a03dd26a48e762edf43a7ad5620061242` |
| sdist | `dist/temporal-managed-nodes-20261105/sdk-artifacts/relf_agent-0.1.0a8+tnodes.3675891f64d0664f.tar.gz` |
| sdist SHA256 | `9b71de40ac48cfdc85547409d278f4f93d5d8816ea07562793fd14ec35ed38f4` |
| 原产品快照 | 459文件，`2c79f1bb86cd9501dd9bf5fca56f7b03c22e09648304fb3305fb59015db6db90` |

构建和安装依赖使用本地 wheel；仅为补齐目录外真实 PG 验证下载与现有环境一致的 psycopg／psycopg-binary 3.3.6，安装命令离线执行，没有访问密钥。wheel 不包含源码专题文档；sdist 文档与测试保留构建时快照，后续文档勘误和最终成绩以当前指南／本记录为准。原包中的3处旧限制／待验描述已在当前源码文档澄清；上述8项复验使用明确同步的修正夹具，不覆盖冻结 sdist 的原测试，修正前后 SHA 另见机器记录。

## 兼容与未授予能力

未配置节点的默认发布不加节点字段，旧无标记普通工具即使名称含相同前缀仍按原工具处理。所选3份旧普通 Agent 流式／审批 History 在原 namespace 的源码及安装包回放通过；旧验证 SDK 的 Worker 注册预检明确拒绝新节点 release，未连接 Service 或调用业务。它们不是任意旧任务迁移的证明。

共享纯规则变动会改变 Coding composition 的 `_pure_sources` 固定指纹；旧 Coding 任务必须使用原包／匹配 Worker，不弱化该保护。首批节点不支持实际 Session／Turn／跨Turn原生历史、Coding composition、部署准入和 parent completion 组合，普通 Tool／Transform 图、循环、reducer 和流式数据流仍未开放。

R04／R08／R19、完整 M1、企业资格、更多平台、真实模型质量和独立采用不因本批关闭。没有推送、触发远端 CI、更新官网或公开发布。
