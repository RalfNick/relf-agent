# Framework Boundary Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Local 节点公共端口漂移和异步检索跨 TTL 返回问题。

**Architecture:** 在已有注册固定与结果采纳边界校验，不增加执行状态、I/O、重试或执行权威。

**Tech Stack:** Python、现有 NodeExecutorRegistry／Knowledge／Vector 端口、pytest、隔离 wheel／sdist。

**Spec:** [维护设计](../specs/2026-11-09-framework-maintenance-design.md)。用户持续优化授权及此前执行方式保持，不新增确认门槛。

## Global Constraints

- 公共六端口与 Temporal 现有范围一致，不递归追踪内部函数。
- 仅最终选中片段 TTL 参与新增向量返回校验；被预算排除的片段不增加误拒绝。
- 不新增来源读取／自动刷新；原 Run／Action／效果／预算／取消／关闭责任保持。
- 原制品与失败不覆盖，网站并行文件不纳入提交；只本地提交，单次跳钩子。

## Review Focus

- 提交后及处理器 await 期间替换输出校验不能成功采纳非法输出。
- 普通无节点 Agent／旧定义和初始合法自定义注册端口保持。
- TTL 边界相等即失效，永久项及尚未过期项保持。
- 公共自定义 Retriever 返回已过期片段不能成为有效引用。
- 恢复已持久化回执不得重复业务调用；修复不授予旧发布任意透明迁移。

## 1. Local 节点端口

Files: `src/relf_agent/local_workflow_nodes.py`、`tests/test_local_node_registry_pinning.py`。

- [x] 提交后和 await 期间漂移的真实 RED；初始自定义与未选注册对照。
- [x] 沿原 `_entry_pin`／`_same_entry_pin` 固定六公共端口，在 `_registry` 核对。
- [x] GREEN、既有节点／恢复模块回归，保留原回执和调用次数。

## 2. Retrieval TTL

Files: `src/relf_agent/vector.py`、`src/relf_agent/retrieval.py`、`tests/test_retrieval_expiry_boundary.py`。

- [x] 受控时钟和真实异步第二来源读取跨 TTL 的 RED；公共 Context 自定义 Retriever RED。
- [x] Vector 最终选中结果和 `_validate_result` 复用 `_validate_expiry`。
- [x] GREEN；永久／未过期／预算排除、无额外来源读取和有效来源重试对照。

## 3. 交付

- [x] 独立审查、相关源码／准确隔离安装同组回归与恢复。
- [x] 冻结准确 wheel／sdist，运行依赖 smoke 和 sdist 产品核对。
- [x] 固定输入的完整离线回归；原10秒崩溃窗口和失败记录保持。
- [x] 同步能力／交付及验收记录，核对原制品、排除网站文件；本地提交以Git记录为准。

已通过阶段证据：准确候选 `0.1.0a8+guards.34d5fe53e3fe66ef` 固定464产品／1580输入；源码／目录外安装33模块同603个ID全部通过、零跳过，JUnit107.505／144.493秒；独立仅运行依赖10条通过，sdist及starter夹具重建的464产品均逐字节一致。所选普通Local／Temporal／节点／Knowledge身份及8个catalog摘要兼容通过，不宣称任意旧History、Session、Coding／部署或私有辅助函数迁移资格。

安装首轮600通过／3个旧RAG starter构建夹具错误原XML保留；只在隔离测试环境补显式build／setuptools／pyproject_hooks及冻结构建输入后，同603项通过，SDK仍从site-packages导入；未增加产品运行依赖。同一冻结输入完整离线自然退出0：15718通过／913条件跳过、零失败／错误，共16631项；JUnit2347.255秒、runner2351.459秒。原Local／数据RED、夹具错误、308份包、全部历史失败及推荐组合保持；本地提交以Git记录为准，未推送或公开发布。完整轮测试ID／恢复窗口及输入完整性按最终机器审计记录解释，不扩大服务、平台或模型资格。

最终审计全部通过：原16598个ID及15685通过／913跳过状态保持，新增33项和本批603项均通过；原五个10秒窗口及两项连接关闭检查通过，464产品／1580输入、308份原包、封存89文件及原完整轮28文件SHA保持，原pytest／guard进程组已退出。准确审计SHA与限定范围见本轮机器记录；不将本机证据扩为新服务、平台或模型验收。
