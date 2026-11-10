# 有界循环验收

2026-11-10，基线 `085c0f5`。本批按有限范围验收完成：增加显式BoundedLoopPolicy、双角色原工厂及无模型完整应用。原Local／Temporal各自唯一执行权威、DTO、绑定和静态DAG环检查保持；不推送、触发远端CI或公开发布。

## 架构与语义

同一不可变纯策略实现原plan／verify。每轮只提出固定iteration节点，统一输入task／previous／iteration，上一轮原结果用Literal固定；不调用caller、开资源、调度或保存第二套循环状态。默认检查done==true，使用原必需input ValueRef／BranchCondition和canonical JSON，不接受I/O谓词。至少执行一次；未满足时replan，达到1..32轮策略上限仍未满足则失败，不能把最后结果当成功。

结果ID不透明，策略不解析后端拼写；原权威负责按轮次提供真实有序已采纳结果，策略检查阶段数量、唯一身份、成员、缺字段及已满足条件后追加。真实执行／恢复另外证明Local rN.step.iteration、Temporal N:iteration、独立Action／effect key与previous。原宿主max_steps／max_revisions／预算／深度可更严格；只有显式同时选择Planner和Verifier才有本组合语义。纯Verifier在保存核验后崩溃恢复中允许重算，不承诺纯策略恰好调用一次，更不能在其内执行业务I/O。

## 分层证据

| 检查 | 实际结果 |
| --- | --- |
| 纯策略 | 有效缺模块RED112失败；同112ID GREEN，相关5模块273通过／0跳过 |
| 配置 | 有效RED57失败／1通过；最终59通过，涵盖SDK双端口、JSON／TOML、Local build／abuild、Temporal原abuild及非默认配置实际执行 |
| Local执行／恢复 | 14通过：1／3轮成功、上限未满足失败、宿主更严限额、第二轮授权／审批重开、unknown核验、取消真实handler和3个原10秒真实进程切点 |
| 最终同ID定向 | 源码／checkout外准确安装同26模块各692通过／0跳过，JUnit99.372／94.882秒 |
| 真实Temporal | 同2ID源码source-fixed／准确安装各2/2通过，JUnit39.980／37.169秒；三轮收敛、第二轮审批静止窗口Worker冷重启、去重与History回放 |
| 纯运行依赖／完整应用 | 15条检查通过，无pytest／Temporal SDK；指南首Python块原文、默认提前结束、非默认条件及未满足上限失败；审批暂停1次／重开新增2次，重复命令零新业务调用 |
| 构建与兼容 | wheel／sdist468产品与构建副本相同；sdist重建468产品一致，重装继续原命令重放；旧FanOut包／新源码／准确安装的普通Local／Temporal Release、默认Planner／Verifier、所选节点／检索和8个catalog一致 |
| 完整离线 | 16001通过／917条件跳过、零失败／错误，共16918项；JUnit2720.455秒，runner2724.571秒，自然退出0 |

完整轮保留旧16731个ID及原通过状态，新增187项；本批692个定向ID在整轮全过。两个新增Service用例离线按条件跳过，其资格来自独立真实服务运行。旧五个10秒恢复窗口与两项连接关闭检查、本批三处修订切点均通过，原7200秒整轮看门狗保持。468产品／1596输入未变，原pytest／guard进程组退出。

真实Service每例plan／verify／work各3、3个不同效果身份／3张回执，每轮previous与原采纳结果一致，每例实际保存并回放8份History后账本不变。12个原始服务pytest／Worker PID均退出，各Service shutdown完成；审批静止阶段首Worker被kill并wait，替代Worker正常退出。模块来源由已通过ready.package==r.__file__及同进程replay import推导，没有独立持久replay路径证明。这里只是确定性只读数学与审计，不能证明任意外部写恰好一次或活跃物理handler全冷恢复。

## 失败保留与准确制品

首个完整轮为16000通过／917条件跳过／1失败，原Coding caller_cancel用例在资源准备后、合成凭据resolve进入前超过原5秒，未认证或提交原生业务，原创建／退休证据保留；精确慢点仍未确认，不能仅凭宿主负载归因。两个默认沙箱隔离复验停在更早的create listener／注册边界，独立AF_UNIX绑定探针得到EPERM；结合原listener代码和五例缺注册记录，推断受限环境阻断了启动，未取得逐例broker stderr直接异常。它们与允许本机Socket的原整轮条件不同，不混为产品回归。纠正验证上下文后，未改产品、测试或5秒门槛，精确1项、原顺序4项、新增Loop前缀接旧模块192项全通过；随后同冻结输入完整复验通过，准确轮次及原XML以机器记录为准。原首轮、受限环境失败和508份相关证据封存不覆盖。最初SQLite只读取证曾生成空WAL／SHM侧文件，业务库正文未写；副作用和mtime已记录，后续采用immutable副本。未合成未知CREATE的fence或重新发CREATE；3个已记录受限复验Popen PID已退出，原待确认意图保留。

首轮source-preflight两例在成功三轮业务后因新夹具访问不存在的held预算字段失败，尚未执行History回放，0份History；不追认为通过。根因是Local与Temporal原预算投影不同。仅修新测试为原reserved／unknown及原关闭字段，同原10秒Activity／20秒ready／30秒观察／120秒单例门槛复验。source-fixed1596输入与最终冻结逐项相同，唯一相对首轮差异为该Service测试；无产品修补。配置初次GREEN两失败是内部prepare夹具缺规范化config，修正夹具后通过；原RED和失败日志均保留。元数据探针首轮又把同步verify错误按异步检查，修正工具synchronous参数，原日志／DB／脚本保留，也不是SDK修复。

| 本批私有制品 | 准确值 |
| --- | --- |
| SDK | `0.1.0a8+loop.1f1b6e386ee578cd`；468产品，1596执行输入 |
| wheel | `dist/bounded-loop-20261110/sdk-artifacts/relf_agent-0.1.0a8+loop.1f1b6e386ee578cd-py3-none-any.whl` |
| wheel SHA256 | `a966e0531837293e21914b75f10f630f6c4106134be2ad0ffbade410a34c48c4` |
| sdist | `dist/bounded-loop-20261110/sdk-artifacts/relf_agent-0.1.0a8+loop.1f1b6e386ee578cd.tar.gz` |
| sdist SHA256 | `6ce4868db6ea027ff03a8939cfe5a71d26c0ed86fb750811210e9659c2211828` |

源码基础版本仍0.1.0a8，隔离构建副本使用唯一私有版本；仅init私有版本按约定不同，安装468产品与该副本相同。包内文档是构建时验收中快照，最终文档不重建已冻结包。原313份包、35份非本批文件及150份封存阶段证据SHA保持。完整原始证据在 `dist/bounded-loop-20261110/`，见机器[索引](../../evals/results/relf-bounded-loop-20261110.json)及[当前交付](../../docs/current-delivery.md)。

使用见[有界循环指南](../../docs/bounded-loop-workflows.md)，设计见[规格](../../docs/superpowers/specs/2026-11-10-bounded-loop-design.md)。本地提交以Git为准，单次跳过钩子；原推荐组合／FanOut／Alpha与历史失败保留，未推送或公开发布。通用带环图、共享状态合并、流式数据流、任意旧History／Session／Coding／部署或私有方法迁移、新平台、真实模型质量、独立采用和完整M1／R01–R26仍不由本批授予；整体对齐见[本轮复核](2026-11-10-bounded-loop-alignment.md)。
