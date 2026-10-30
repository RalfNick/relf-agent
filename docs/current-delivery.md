# 当前本地交付

更新：2026-10-30。本页是当前交付的唯一入口；其余状态页、历史队列及原 Alpha 清单不定义本轮待执行任务。此前已按授权使用RalfNick将`4af364b`、`5951265`及其祖先推送到远端main，保留[skip ci]；推送后核对两个提交的CI运行数均为0。当前接入目标下的必要变更仅本地提交，不再推送、触发远端CI、部署或公开发布。源码推送不等于上传私有wheel或授予平台／发行资格。

## 当前候选与来源

本轮只处理bf65e58审查的一个P2和四个P3，已从准确提交离线构建并冻结独立候选。同包风险回归、仅核心依赖安装、内部恢复演练和最终只读审查均已通过；旧包及其验收保持原范围。

| 项目 | 固定值／状态 |
| --- | --- |
| 已推送源码 | `5951265caf2bc0dbd4a0d820325e5f4fe8b08adc`，包含修复来源`4af364b`及原`bf65e58`；推送未上传私有wheel |
| 新候选源码 | `4af364b403ed9ee01487cc8eb571d242a5bece7b`；以bf65e58为基线，六个Facade／事件校验文件改变 |
| 候选版本 | `0.1.0a8+maintenance.0608576182db502f` |
| 推荐 wheel | `dist/public-preflight-fixes-20261030/private-artifacts/relf_agent-0.1.0a8+maintenance.0608576182db502f-py3-none-any.whl`，已冻结 |
| SHA256 | `082b5ec9d1c107539b925d8a9f1332560eb7f92ec518b0e603ad02b5046cb482` |
| 产品 | 451文件，源码树摘要 `0608576182db502fc2efbe3bf9a3abc26dafda392f05ec0e386a6657cd0cbc69` |
| 版本约定 | 源码基版本保留0.1.0a8；隔离构建副本同时固定发行元数据、模块版本与CLI为上述唯一私有后缀；不修改旧包 |
| 本轮状态 | 五项修复及所选本地交付门槛闭环，候选已冻结；没有新的索引安装、平台或公开发行资格 |
| 真实独立采用 | 待验证；内部演练不代签独立参与者的自有业务 |

原候选`.18718c3c5a9e9882`及其SHA／原制品保留，准确历史入口见[bf65e58冻结页](https://github.com/RalfNick/relf-agent/blob/bf65e584a039d9b2f24814ac5f48bcc9f848bbcd/docs/current-delivery.md)和[原稳定交付验收](../architecture/reviews/2026-10-30-stable-local-delivery.md)。不得以新包覆盖原包或改写其成绩。

## 安装与依赖

将下方绝对路径替换为本机实际文件，从新的空目录执行；最终验证状态以本页门槛表为准。先按上表核对文件 SHA256；文件与版本不符即停止，不从索引寻找同名替代包。

```bash
mkdir my-relf-adoption
cd my-relf-adoption
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install /ABS/relf-agent/dist/public-preflight-fixes-20261030/private-artifacts/relf_agent-0.1.0a8+maintenance.0608576182db502f-py3-none-any.whl
python -m pip check
python -c 'import importlib.metadata as m, relf_agent; print(m.version("relf-agent"), relf_agent.__version__, relf_agent.__file__)'
relf --version
relf init app
cd app
python -m agent_app --ticket INC-001
```

发行元数据、模块与CLI必须显示相同完整私有版本；模块应来自新环境site-packages。默认依赖仍为httpx与jsonschema，不需Redis／Temporal／Docker／模型密钥。依赖锁和本地wheelhouse是验收环境证据，不是新增的运行依赖。

可选功能按[安装指南](installation.md#可选能力)选择extra，并以本页精确wheel路径安装，不用原a8文件名。语义RAG显式使用[原神经模型配置](phase1-semantic-rag.md)；默认连续教程使用词法检索，不自动下载权重。模型／异步工具／记忆替换见[连续应用](support-journey.md#继续定制与恢复)，组件扩展方式与限制见[扩展指南](extending.md#先选择扩展方式)。

已有Run保持原数据库、command_id、定义、工厂与资源配置；不要用不同版本覆盖其环境。审批绑定原Action和摘要，回执保存后按[恢复指南](recovery-guide.md)在新进程继续；原模型响应和已接收业务回执不重新派发。此候选不自动接管任意旧Temporal Worker／History。

## 冻结支持范围

| 组合 | 本轮沿用能力 | 资格与限制 |
| --- | --- | --- |
| Local 单Agent／Session | 显式Provider、可信Python工具、SQLite持久事实、串行Turn、审批与原配置恢复 | Scope由宿主可信提供；执行credits不是货币费用；不新增队列或认证系统 |
| Local 上下文／记忆／RAG | 原Session／Facts／Knowledge／Artifact职责、词法默认与显式语义参考应用 | 真实语义需要原明确模型与来源验证；不是任意语料质量、冲突治理或自动数据生命周期 |
| Local Plan／Team | 原规则DAG／固定Supervisor、受管理成员、父级回执验证和恢复 | 不称自主模型规划或任意团队策略质量 |
| Local Tool图 | 显式providers={}，既有Tool Action与async handler、预算／审批／未知效果核验 | 普通Agent仍需要Provider；不是通用节点／reducer或逐记录流式Workflow |
| 事件与展示流 | 原游标订阅、opt-in模型文本／异步工具JSON展示、原响应／回执结束标记 | 默认关闭；展示不采纳提案、不确认效果、不替代业务终态或实际处理器结束 |
| Temporal | 原History是唯一执行权威；新增流只沿用已验收原生文本Agent子集 | [既有真实Service证据](../architecture/reviews/2026-10-29-stream-batch-freeze.md)按原包复用；不新增高级流组合／在途Activity窗口／真实业务写或新后端资格 |

Harness继续只准备与提案，不派发模型／工具或提交状态。Local／Temporal各自推进，效果回执、预算结算、unknown和真实处理器结束分别核对。通用节点／reducer、多模态、更多Temporal组合、跨宿主／HA及企业治理仍在[长期清单](remaining-work.md)，不因本轮冻结自动解锁。

## 本轮门槛、阻塞与唯一下一步

| 门槛 | 当前状态与证据 |
| --- | --- |
| 确认问题修复 | 原代码27个预期反例失败／11控制通过，补充context body-error拒绝回归；新旧相关247项通过，原失败保留 |
| 新候选源码／隔离安装 | 64选择项／1002节点已冻结，旧937与原Alpha370精确ID完整保留；源码／精确隔离安装各1002通过，零失败／错误／跳过，分别303.01／286.87秒；保持同一原服务排除项，警告即错误，不标全量SDK通过 |
| 默认应用／兼容恢复 | 新精确wheel在空目录执行30条独立进程命令通过（19.94秒自动执行）；实际Provider／工具替换、审批前零效果、重复回执、进程重启及原候选`.18718c3c5a9e9882`↔新候选双向有限Local恢复均通过；不计真实模型或独立采用／性能SLO |
| 模型／外部服务 | 不改Provider、Engine、工具执行或History协议；冻结后核对不变路径，再复用原版本的[78/78质量](../architecture/reviews/2026-10-29-default-task-quality.md)及所选原Service证据，不重标为本包重新调用 |
| 最终审查／一致性 | 只读审查未发现Critical／Important／Minor问题，独立重跑41项新回归通过；Ruff、格式、Git空白、26个相对链接及源码／安装字节核对通过，10份原制品和204份历史数据库保持原哈希 |
| 外部独立采用 | 待验证；流程与记录模板见[独立接入](independent-onboarding.md)，与本地工程冻结分开 |
| 平台／公开发布 | 本轮不执行；原a8／dev19所选S2／函数指纹各保留原制品与失败，不新签资格 |

公共run拒绝无效等待参数时不受理业务；有效run及已受理Run的观察取消语义不变。owned Agent的参数／来源预检失败不关闭入口，真实关闭开始后仍停止接收并保留清理重试。资源回调重入Facade沿原Context来源保护拒绝，外部并发关闭观察仍共享原关闭任务。事件时间参数保留原有效范围。

核心依赖新环境未安装Temporal SDK，默认应用审批／重启／重复回执同样通过；这不授予Temporal平台或真实模型资格。

本批本地工程收尾已完成，不扩大已选支持范围。后续独立采用、更多平台和公开发布继续单列，需分别取得实际证据与相应授权；历史三批及原观察成本诊断不重新开发。

逐项修复、原失败及覆盖范围见[本批验收](../architecture/reviews/2026-10-30-public-preflight-fixes.md)。构建源码固定在上表，后续仅记录文档，不以文档提交重建原wheel。
