# 当前本地交付

更新：2026-10-30。本页是当前交付的唯一入口；其余状态页、历史队列及原 Alpha 清单不定义本轮待执行任务。只在本地提交，不推送、远端 CI、部署或公开发布。

## 当前候选与来源

本轮已从下列准确提交离线构建并完成同包源码／安装回归、内部接入、有限兼容验证及最终只读审查，随本地提交冻结工程目标。历史真实质量、平台与公开发布状态保持各自范围。

| 项目 | 固定值／状态 |
| --- | --- |
| 源码基线 | `16d21fda99e6fb002f23c24140ff35f9d27f078b`；相对`11fa206`仅 `agent_runtime.seconds` 的非法数值拒绝逻辑改变 |
| 候选版本 | `0.1.0a8+maintenance.18718c3c5a9e9882` |
| 推荐 wheel | `dist/stable-delivery-20261030/private-artifacts/relf_agent-0.1.0a8+maintenance.18718c3c5a9e9882-py3-none-any.whl`，已冻结 |
| SHA256 | `23cf675c2fb686e35ff0bfde5283000c08aafb4537e1b917899cd26dcfe10044` |
| 产品 | 451文件，源码树摘要 `18718c3c5a9e9882a3a5c7fc74489e41a9dfd62f93e9eb0ae39b61f424c2ec5f` |
| 版本约定 | 源码基版本保留0.1.0a8；隔离构建副本同时固定发行元数据、模块版本与CLI为上述唯一私有后缀；不修改旧包 |
| 发布状态 | 工程门槛与最终审查通过，随本地提交冻结；没有索引安装、平台或公开发行的新资格 |
| 真实独立采用 | 待验证；当前没有未参与开发的业务接入者，不用内部演练代签 |

## 安装与依赖

将下方绝对路径替换为本机实际文件，从新的空目录执行；最终验证状态以本页门槛表为准。先按上表核对文件 SHA256；文件与版本不符即停止，不从索引寻找同名替代包。

```bash
mkdir my-relf-adoption
cd my-relf-adoption
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install /ABS/relf-agent/dist/stable-delivery-20261030/private-artifacts/relf_agent-0.1.0a8+maintenance.18718c3c5a9e9882-py3-none-any.whl
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
| 确认错误修复 | 原共享guard的10个OverflowError反例；Local／Temporal／Profile／关闭／观察语义相关73项通过，原失败保留 |
| 候选源码／隔离安装回归 | 60个选择项共937个节点已冻结，含原Alpha的370个精确测试ID；源码／隔离安装各937通过，零失败／跳过，分别298.70／291.24秒；原同一项服务测试明确排除。警告即错误，无放宽原选择；不拼成全量SDK资格 |
| 默认应用与兼容恢复 | 内部演练30条独立进程命令通过：替换模型／工具、审批前零效果、重复回执、重启恢复及旧私有包与候选的Local双向恢复；应用实际替换Provider类、决策参数和工具结果，回读原响应usage及工具回执确认；30条自动命令24.48秒，不是用户接入时间或SLO；第一轮仅改identity的20.07秒演练另行保留 |
| 模型／外部服务 | 本轮没有改变派发／协议／模型配置；逐文件核对未变路径后复用[原78/78质量](../architecture/reviews/2026-10-29-default-task-quality.md)及所选原Service证据，不改它们的版本资格 |
| 外部独立采用 | 待验证；流程与记录模板见[独立接入](independent-onboarding.md)，与工程冻结分开 |
| 平台／公开发布 | 不执行；原a8／dev19所选S2／函数指纹各保留原制品、门槛与失败，不新签资格 |

本轮工程门槛与最终审查已通过，随本地提交结束，不自动追加开发。唯一接入后续是由未参与开发者按独立流程实际接入并填写记录；目前保持待验证，不以外部参与者缺失追加功能。历史三批及观察成本已在`11fa206`收口，不重跑已通过且未受影响的工作，不继续无产品热点证据的性能调整。

本轮实现、失败、门槛与证据复用映射见[稳定交付验收](../architecture/reviews/2026-10-30-stable-local-delivery.md)。源码构建提交固定在上表；本页冻结记录的提交可用`git log -1 --format=%H -- docs/current-delivery.md`核对，不需要重建wheel。

最终只读审查无Critical／Important／Minor项，独立重跑21项针对性检查通过，并核对候选、两套937报告、原370ID、9旧制品和204库。其范围排除与八项最终核对见[验收记录](../architecture/reviews/2026-10-30-stable-local-delivery.md)。
