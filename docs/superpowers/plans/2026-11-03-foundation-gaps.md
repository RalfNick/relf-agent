# 基础能力缺口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 两个独立实现并行推进，主任务统一做一次整批审查与集成验收。

**Goal:** 补齐固定 HTTP GET 查询及现有增量流的版本化 Profile 配置。

**Architecture:** 复用 HTTPToolSource／ToolRegistry 和组件注册／Builder；不改变 Local／Temporal 执行权威、Manifest 默认值或取消语义。

**Tech Stack:** Python 3.11+、httpx、jsonschema、pytest；不新增依赖。

**Spec:** [基础设计](../specs/2026-11-03-foundation-gaps-design.md)

## Global Constraints

原 POST identity 不变；省略 stream_updates 不改原 Manifest。所有新配置在分配前校验。保留历史制品／失败，禁止推送、远端 CI、官网部署和公开发行。保留原未跟踪 review，不代为提交。用户已授权持续执行，按既有并行方式推进；本批不申请新的发布或账号操作。

## Review Focus

1. GET 查询编码不能让参数改变 authority／路径，不能静默丢掉 null／空列表／未映射参数。
2. URL 百分号编码可能比 JSON 更长，必须限制实际查询字节；响应错误不泄漏参数。
3. 取消等待不能提前释放仍活跃的 HTTP 线程，原关闭可重试。
4. Profile 默认不能隐式启用流／改变旧身份；无效配置不能留下数据库／客户端。
5. 新配置的观察取消、旧 Run 重连和策略漂移继续遵循原恢复契约。

## Task 1: HTTP GET 与固定参数映射

**Files:** http_tools.py、http_tool_transport.py、http_tool_factories.py；新增 tests/test_http_get_tools.py；docs/http-tools.md。

**Interfaces:** 原 HTTPToolSource 新增 keyword-only method="POST"／query_parameters=None；原 tools/http-json 使用同字段。Transport 原调用兼容。

- [x] 写本机服务反例：实际 GET、Unicode／空白／特殊字符与重复键、零 body、非法输入零请求和编码超限；运行并保存 RED。
- [x] 最小实现固定配置与编码，默认 POST 分支保留原 identity、调用和请求格式。
- [x] 补 JSON／TOML、原审批关闭重开／同命令去重，以及请求取消／关闭重试测试；不改原期限。
- [x] 运行新增及原 HTTP／ToolSource／CLI 相邻测试，更新 HTTP 指南。

## Task 2: 既有 StreamUpdatePolicy 的 Profile 装配

**Files:** runtime_config.py、runtime_builder.py、新增 stream_update_factories.py（若符合原工厂组织）；新增 tests/test_stream_update_configuration.py；docs/agent-stream-updates.md。

**Interfaces:** components.stream_updates 的 bounded 工厂返回原 StreamUpdatePolicy；Local／Temporal 原 Builder 通过 **options 传入。没有新 Provider wrapper 工厂。

- [x] 写 JSON／TOML 与 sync／async Local 配置工具增量反例，证明当前配置缺失；保存 RED。
- [x] 注册纯 bounded 工厂，允许新 component kind，复用原四项字段校验和默认值。
- [x] 补非法配置零分配、缺省身份保持、变更拒绝／原配置恢复／重复命令事件不重发、观察取消不取消 Run；Temporal 离线装配／Manifest 一致性。
- [x] 运行新增及原流、装配和 Temporal Profile 相邻回归，更新显式模型流与清理边界说明。

## Task 3: 集成、安装与能力记录

**Files:** docs/remaining-work.md、docs/implementation-status.md、docs/continuous-development.md、architecture/reviews/2026-11-03-foundation-gaps.md。

- [x] 检查两个独立文件范围，统一审查公共配置、默认身份、错误／取消／恢复；重要问题以反例闭环，不追加无关功能。
- [x] 完成相关测试／Ruff／格式／Git 空白检查；在独立构建目录产生私有验证 wheel／sdist，checkout 外 venv 安装后运行相同选择与 CLI smoke。
- [x] 比对安装产品与当前源码，核对原21制品哈希及用户未跟踪文件，记录具体结果、未验收范围和产品包身份。
- [x] 同步当前能力入口，保留原推荐包与历史，不自动发布新Alpha。本批结果交付为工作区和本地验证材料；未明确要求提交时不新增 Git 提交。

实际结果：源码／准确安装各440项，运行依赖10命令、POST双向恢复2场景、452产品与290原制品核对通过。独立审查1项P2经3个RED→GREEN闭环；初次验收时未新增Git提交／推送。详见[验收](../../../architecture/reviews/2026-11-03-foundation-gaps.md)。

提交授权补记（2026-11-03）：用户明确要求本轮改动、测试与文档本地提交，单次跳过钩子；原制品、构建快照及历史记录保持，不推送或公开发布。
