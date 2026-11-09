# Close Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为原 CloseIncomplete 增加可操作、脱敏且不取得执行权威的关闭诊断。

**Architecture:** 错误保留原 report，元数据仅为已有生命周期事实的安全副本。Facade／构造／Assembly 补原阶段，CLI 输出同一快照。

**Tech Stack:** 既有 Python／asyncio／SQLite／pytest，无新增依赖。

**Spec:** [关闭诊断规格](../specs/2026-11-09-close-diagnostics-design.md)。Root 已确认此最小方案，执行阶段无额外产品范围决策。

## Global Constraints

- 原 code／message／report 和取消／关闭／恢复契约保持；不修改容量 owner 文件。
- metadata 仅固定枚举与实际非负整数，无原异常正文／路径／ID／秘密。
- 不为 Runtime 新增诊断属性，不包裹其他旧异常，不改关闭顺序。
- 本代理不提交、不碰 website／他人文档／原制品；Root 统一验收与单次本地提交。

## Review Focus

- 任意恶意或敏感 report 不被序列化或 repr。
- False 不能作为计数0；未知不能被写成零工作。
- 上层阶段不覆盖下层真实 handler／ACK 诊断。
- 关闭观察取消仍为 CancelledError，原处理器与租约保留。
- SDK 副本修改不能改变下次诊断，CLI 其他错误输出保持。

## 1. 错误契约与安全投影

- [x] 新增 tests/test_close_diagnostics.py，先验证 legacy report、脱敏、真实枚举／计数与副本隔离 RED。
- [x] 新增 close_diagnostics.py，扩展 errors.py；运行同一用例 GREEN。

## 2. 原生命周期接入

- [x] 新增 tests/test_close_diagnostics_lifecycle.py，先验证真实 Local 工具、Temporal RPC、Builder、Assembly 的失败／取消重试 RED。
- [x] 修改 agent_runtime.py、temporal_agent_runtime.py、temporal_builder.py、temporal_assembly_lifecycle.py，仅补诊断阶段与原异常元数据。
- [x] 同例 GREEN，并运行既有生命周期／关闭／清理回归。

## 3. CLI 消费与交付

- [x] 新增 tests/test_close_diagnostics_cli.py 先验证 text／JSON 的安全信息及其他错误原样 RED。
- [x] 修改 cli.py 的 CloseIncomplete 输出分支，运行 GREEN。原 RuntimeBuildError 仅直接 CloseIncomplete cause 追加投影，保持原错误与 cleanup。
- [x] 将精确接口／证据交 Root；目录外准确安装884项、完整源码15685通过／913条件跳过、文档与所选兼容核对已完成；源码／安装同5个Service ID独立各5/5记录，不以离线跳过代签。本地提交以Git记录为准，未推送或公开发布。
