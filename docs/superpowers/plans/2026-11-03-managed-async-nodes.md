# 通用受管理异步节点实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 独立 Registry 和纯编译任务并行，主任务统一 Local 集成、恢复及一次整批审查。

**Goal:** 交付 Local Workflow 的通用 NodeExecutor、原 Action 恢复及配置／安装后使用路径。

**Architecture:** 公开 executor 声明纯 lower 到原 Tool v2／并行 v3；私有注册与固定执行适配器复用同一 Engine 效果循环，普通工具和 Agent 权限不变。

**Tech Stack:** Python 3.11+、原 httpx／jsonschema；不新增依赖或数据库 Schema。

**Spec:** [设计](../specs/2026-11-03-managed-async-nodes-design.md)

## Global Constraints

基线e75c756；Local／Temporal唯一执行权威不变；Temporal新组合预检拒绝。保留旧定义／计划／未选能力Manifest字节。原制品、历史失败和用户原未跟踪review不改。完成后仅本地提交，单次core.hooksPath覆盖；保留skip ci，不推送／远端CI／部署／公开发行。用户已明确授权执行，不另设设计审批或阶段解锁。

## Review Focus

- 私有alias不得借Agent.tools／tool_set／普通Tool节点扩大权限或绕开原plan归属。
- 注册对象、async callable、方法代码及返回序列化期间漂移不能绕过固定身份。
- receipt_received及Action完成窗口恢复不能重复execute／reconcile，null结果与无证据不同。
- 原输出Schema失败仍保留完成效果／预算，取消不代表业务回滚或真实结束。
- lower／from_plan／并行frame不能重复包装输入或改变旧v1–v3字节；嵌套InputMap有界。

## Task 1: 结构化节点端口与私有Registry

**Files:** 新workflow_executors.py、workflow_node_factories.py；新tests/test_workflow_executors.py。

**Interfaces:** NodeExecutor／NodeReconciler、NodeExecutorSpec、NodeExecutorRegistry、IdentityNodeExecutor；alias `__relf_node__:`。Registry.register(spec, component)、tool(alias)、manifests(aliases)、manifest(aliases)、validate_output(alias, result)、executor属性及纯check。不得暴露到公开ToolRegistry。

- [x] 写第三方async完整JSON／config、Schema、显式effect、形状／identity／代码漂移、queryable reconcile null与未知、默认实现反例并运行RED。
- [x] 实现固定注册和私有Tool执行适配；真实execute／reconcile前后及JSON采纳复核，不增加状态机／生命周期。
- [x] 私有适配器返回原EffectObservation，Spec.output_schema延后由Workflow完成边界调用validate_output。
- [x] 同步identity工厂空config预检、原自定义factory可替换；相关单测转绿。

## Task 2: 公开声明与纯lowering

**Files:** workflow.py；新tests/test_workflow_async_definitions.py。

**Interfaces:** GraphNode.executor可选；共享lower_node把executor变成Tool alias+InputMap(input/config)，GraphWorkflowSpec保留公开声明；ExecutionPlan不接收未lower executor。旧v1/v2/v3不变，from_plan幂等。

- [x] 写旧字节与新声明、非对象输入、嵌套InputMap／深度限制、串行v2／并行v3、from_plan幂等反例，运行RED。
- [x] 最小实现新四选一节点、有限递归InputMap和纯编译；新字段只在选用时输出。
- [x] 运行workflow／scheduler／definitions相关回归，不改调度或Engine。

## Task 3: 原Local Action集成与配置

**Files:** engine.py、workflow_runtime.py、workflow_parallel.py、runtime_config.py、runtime_builder.py、temporal_profile.py、__init__.py；新tests/test_workflow_async_nodes.py、test_workflow_async_configuration.py。

**Interfaces:** LocalEngine(workflow_executors=None)。原plan归属校验后查私有registry／executor；workflow Manifest仅增加选定注册及协议，Tool成本／审批／接收采纳仍原路径。公开tools保持原值。

- [x] 先写无模型async节点、混合图／并行／绑定、审批／授权／预算、私有名称隔离和自定义ToolExecutor路由反例，保存RED。
- [x] 集成manifest分public/private，原coding／input专用扫描只看public；节点完成后校验Spec输出，再校验节点输出。
- [x] 增加Local sync／async组件装配和JSON／TOML默认／替换；Temporal组件及递归请求／Worker入口执行前拒绝。
- [x] 执行相关回归，检查NodeEngine继承原注册、from_plan不重复包裹、嵌套Team／Dynamic图恢复。

## Task 4: 恢复、隔离安装、文档与提交

**Files:** 新进程崩溃fixture与recovery测试；docs/managed-async-nodes.md、static-workflows／能力状态／当前交付；本批architecture/reviews及evals/results。

- [x] 先写真实进程intent／外部效果／receipt／Action完成四窗口、四类效果／null核验、取消继续执行与关闭重试，RED→GREEN；保留失败和原期限。
- [x] 一次独立整批审查；重要问题一次反例修复，不顺带添加循环／数据流／分布式能力。
- [x] 相关源码／准确安装同测试ID、旧包双向默认恢复、最小运行依赖、wheel／sdist／源码一致、Ruff／格式／空白核对。
- [x] 原制品和用户文件哈希核对，说明Local支持及Temporal待验收、更新能力文档；冻结本地验证候选。
- [x] 显式暂存本批文件，单次跳过钩子本地提交并核对提交内容／持久hooks不变；不推送或公开发布。

## 执行记录（2026-11-04）

Registry／编译／Local／配置具有保留的实现前 RED；恢复 13 项及取消 6 项在集成后首次运行通过，不声称存在未记录的故障矩阵 RED。一次独立审查的一项 P2 以 9 个有效反例 RED→GREEN 闭环；原审批回执规则保持，在派发前拒绝漂移。初始相关源码／准确安装各 997 项相同 ID 通过，最小依赖与 sdist 10 条命令、跨版本 26 个进程、示例 5 个进程通过。最终 README 元数据修复后的准确包另冻 .nodes2，源码／安装各 1003 项相同 ID 通过；运行依赖／sdist、兼容和示例按新包串行重验。首轮全量为15303通过／895跳过／8失败：6项基线README链接修复，2项旧10秒崩溃夹具超时在原期限下三轮5/5通过，但根因与整轮时序仍待验证，不声明全库绿色。原失败、首包与所有日志保留。最终本地提交的Git回执记录在忽略证据目录，不推送或公开发布；永久hooks路径保持。
