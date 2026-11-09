# Node Executor Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 固定 NodeExecutor v1 core 黑盒检查与安装后自检路径。

**Architecture:** fixture 提供真实组件和故障；新角色沿原 AdapterContractSuite，LocalEngine／Tool Action 仍是唯一执行权威。独立 SQLite 参考供显式离线选择。

**Tech Stack:** Python 3.11+、SQLite、现有 NodeExecutorRegistry／AdapterContractSuite、pytest。

**Spec:** [设计](../specs/2026-11-09-node-executor-contract-design.md)。

## Global Constraints

- 原四角色 catalog／status codes／摘要与默认 CLI 保持；不改变执行后端、恢复或取消语义。
- core 仅 Local 读取型 fixture，不授予写、Temporal、模型、外部采用或完整 R25 资格。
- 原制品／失败／受保护审查文件保持；仅本地提交，单次跳过钩子，不推送／公开发布。

## Review Focus

- fixture 伪造 verdict 或缺少回调不能认证；每个 verdict 要有真实调用／原 Store 依据。
- identity／method漂移、非法输入、取消后隐藏工作与失败关闭。
- 没有 fixture 时零 I/O；合法 null 输出和输入／config 分离。
- 新角色不得误入原 model dispatcher；旧摘要逐项字面验证。
- 原 borrowed／owned 资源与取消任务完成前不得释放 workspace。

## 1. 固定角色与入口

- [x] 在 test_node_adapter_contract_catalog/cli 先 RED：新角色10项，旧角色摘要不变，显式离线才运行。
- [x] 修改 adapter_contract_catalog、adapter_contracts、adapter_contract_cli，显式 Node dispatch；不改公共 DTO／status codes。
- [x] 新 catalog 和原 catalog／CLI 回归通过。

## 2. 真实核心检查

- [x] 新 node_adapter_contract.py 中实现 Spec 的 NodeContractResource／Pause／Session／Fixture 和 run_node_case(case_id, fixture, workspace)。测试先 RED。
- [x] N01–N10 使用真实 Registry／Local Engine，缺失管理端口保留 not_verified；错误脱敏、原清理 pending 可重试。
- [x] 反例覆盖错误 fixture／虚假通过／不合法返回／漂移／输出保存和取消关闭。

## 3. 参考与首用

- [x] node_adapter_contract_reference.py 提供独立 SQLite 组件及 offline_node_fixture()；参考测试先 RED。
- [x] examples/node_executor_contract.py 提供可编辑的独立组件与实际配置，CLI／SDK同10检查通过。
- [x] 导出必要公共类型，补使用与替换文档，不增加执行权威。

## 4. 交付

- [x] 源码受影响回归、目录外唯一私有 wheel 同ID、运行依赖及 sdist 产品一致验证。
- [x] 完整离线回归与独立审查；保留原失败、区别实际未验证资格。
- [x] 同步当前交付／R25／验收记录。交付约束固定为本地提交、单次跳过钩子、不推送；最终提交以 Git 为准。
