# Bounded Loop Implementation Plan

> **For agentic workers:** Execute the agreed parallel workflow on disjoint owned files, with TDD and independent read-only review. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 提供可配置、可恢复的有限执行／结果检查循环。

**Architecture:** 同一纯BoundedLoopPolicy实现原plan/verify；原Dynamic DAG逐轮执行，Local／Temporal各自唯一权威。

**Tech Stack:** Python、原PlanningRequest／DAGProposal／BranchCondition／Literal／Verification、SQLite、缓存Temporal、pytest。

**Spec:** [设计](../specs/2026-11-10-bounded-loop-design.md)。

## Global Constraints

- 不修改Engine、DAGRuntime、TemporalParentState、默认策略整表、DTO或绑定格式；静态DAG仍拒绝环。
- max_iterations严格int1..32；until只用required input ValueRef，原canonical比较；无I/O或隐式caller调用。
- 调用身份不透明，原权威提供有序已采纳history；无新状态／队列／执行后端。
- 原权限、预算、审批、unknown、取消、真实关闭／恢复期限保持；同包，不借旧成绩。
- 原制品、失败和35份非本批内容保持；原缓存服务，原10秒子进程和7200秒全轮门槛。
- 用户已选择自主并行执行和单次跳钩子本地提交；不推送／发布，不新增另一批能力。

## Review Focus

- bool与number不可混同，null合法；缺条件证据、额外结果／重复身份／越界revision应明确拒绝。
- plan与verify的阶段结果数不同；无剩余步骤不能阻止已完成结果的成功核验。
- 已经满足停止条件后的历史不得继续运行，最大轮数未满足必须失败。
- 每轮原身份／审批／预算独立，重放不重复业务；上一结果必须是已采纳的固定副本。
- 未显式选择时原默认整表、普通Local／Temporal发布与已选节点／检索元数据保持。

## Task 1: 纯策略

Files: `src/relf_agent/bounded_loop.py`，`tests/test_bounded_loop.py`。

Produces: BoundedLoopPolicy exact constructor、plan、verify和不可变identity；逐轮统一输入与原DAG/Verification。

- [x] 写配置／条件／history／constraints／终止／上限／副本与替换的测试，实际运行有效缺模块RED并保存。
- [x] 实现设计精确边界、GREEN；对照原绑定与canonicalbool/null语义，不运行caller。
- [x] 独立复核设计与质量，无P1/P2后冻结该文件，不自行Git。

## Task 2: 显式装配

Files: `src/relf_agent/bounded_loop_factories.py`，`runtime_builder.py`，`__init__.py`，`tests/test_bounded_loop_configuration.py`。

Consumes: Task1的BoundedLoopPolicy。Produces: SDK导出及planners/plan_verifiers各bounded-loop工厂，返回同名map。

- [x] SDK／JSON／TOML、Local build／abuild和Temporal abuild的缺实现RED；非法值在数据库／资源创建前拒绝。
- [x] 严格解析原until条件绑定并注册两个显式工厂；自定义worker／until／max_iterations实际执行，GREEN。
- [x] 对照前包默认表、普通发布与所选catalog摘要；独立复核，不改默认整表或提交。

## Task 3: 原执行与恢复

Files: `tests/test_bounded_loop_execution.py`，`tests/bounded_loop_worker.py`，`tests/test_bounded_loop_temporal_service.py`，`examples/bounded_loop_workflow.py`。

Consumes: 前两任务；使用原受管理Graph成员／父子Run，业务账本独立于执行库。

- [x] Local实际收敛／提前停止／末轮失败、预算／host更严限额、审批／unknown／取消；独立核对逐轮业务调用与效果身份。
- [x] 原10秒真实进程切点覆盖首轮核验保存／replanning交接／下一提案采纳；恢复不重做已完成轮次或污染previous。
- [x] 正常及第二轮审批等待Worker冷重启的真实Temporal测试、重复命令与History重放；只收集不启动服务，由root串行运行。
- [x] 示例支持暂停／重开／重复，准确安装后checkout外执行；无模型、原实际业务计数，独立审查后冻结。

## Task 4: 验收与交付

Root负责指南、能力／交付入口、验收与机器记录，以及dist控制器。

- [x] 同步[有界循环指南](../../bounded-loop-workflows.md)及当前范围，保留旧FanOut与历史正文；展示可直接运行的SDK／配置和完整应用。
- [x] Ruff／格式／空白与同组源码回归；真实Temporal服务先确认源码，冻结产品／执行输入及owned路径。
- [x] 唯一私有wheel／sdist、目录外准确安装同ID、原文指南／应用、纯运行依赖、sdist重建比对、所选旧元数据兼容；准确安装真实Temporal同ID验证。
- [x] 同冻结输入完整离线回归，原16731 ID保留、原通过状态保持、旧五10秒窗口与资源退出／历史SHA核对。
- [x] 按实际结果更新文档／机器记录，独立最终复核；仅本批文件本地skip ci提交，单次跳钩子，不推送或公开发布，最终以Git记录为准。
