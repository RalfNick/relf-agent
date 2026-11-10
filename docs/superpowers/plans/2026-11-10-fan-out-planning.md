# Bounded Fan-Out Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 提供可配置、可恢复的有限列表分发／汇总默认 Planner。

**Architecture:** 纯新策略提出原 DAG；Local／Temporal 保留各自唯一父子执行权威，既有注册默认不增加成员。

**Tech Stack:** Python、PlanningRequest／DAGProposal／ValueRef／InputMap、原工厂、pytest、SQLite与缓存Temporal CLI。

**Spec:** [设计](../specs/2026-11-10-fan-out-planning-design.md)。用户持续开发及并行实施方式保持。

## Global Constraints

- 不修改 Engine、DAGRuntime、TemporalParentState 或默认planner字典；不新增绑定格式。
- 无 reducer max_items 1..256，有 reducer 1..255；path至多31段；初始 revision=0/results为空。
- 稳定map-0000键与可选reduce节点；不改变原 Action、预算、审批、取消、unknown／关闭协议。
- 不下载服务或调用付费模型；复用缓存Temporal，只启停本轮自己创建的服务与Worker。
- 原包、失败、网站及他人未跟踪文件保留；仅本地提交，单次跳钩子，不推送／发布。

## Review Focus

- 原请求／配置的嵌套对象修改不能改变已生成计划或组件身份。
- 列表索引路径和max_nodes／remaining_steps不一致时拒绝，不能截断或先派发。
- 并发完成顺序不改变汇总映射，汇总不能在审批／未知子结果前运行。
- 提案／原子回执恢复不重新规划或重复已完成业务。
- 未显式选择新策略时 Local／Temporal 默认发布、旧DTO与工厂身份保持。

## 1. 纯 Planner

Files: `src/relf_agent/fan_out_planning.py`、`tests/test_fan_out_planning.py`。

- [x] 缺实现真实RED；配置／路径／成员／条数／constraints／revision拒绝，以及确定性计划对照。
- [x] 实现设计中的签名、不可变identity、原绑定和DAGProposal，GREEN；不做I/O。

## 2. 显式装配

Files: `src/relf_agent/fan_out_factories.py`、`src/relf_agent/runtime_builder.py`、`src/relf_agent/__init__.py`、`tests/test_fan_out_configuration.py`。

- [x] SDK导出与JSON／TOML、Local build／abuild及Temporal abuild装配RED（保留原异步Temporal入口）。
- [x] 仅注册显式planners/fan-out工厂，返回同名映射；非法配置在装配前拒绝，GREEN。
- [x] 核对不选择时原默认注册和普通发布身份保持。

## 3. 原执行链路验收

Files: `tests/test_fan_out_execution.py`、`tests/test_fan_out_temporal_service.py`、必要独立worker helper、`examples/fan_out_workflow.py`。

- [x] 真实Local并发／无汇总与显式汇总／权限审批／额度／取消／unknown和可替换组件。
- [x] 原SQLite提案保存／采纳／部分子结果恢复和重复提交／审批，业务回执计数不重复。
- [x] 原Temporal服务／Worker运行及History重放，至少验证正常批处理和审批／重启恢复；其他故障按实际证据限定。
- [x] 示例准确安装后从checkout外运行，省略模型可完成业务。

## 4. 固定交付

- [x] 独立设计／代码审查、Ruff与定向回归，保留所有RED和失败。
- [x] 唯一候选wheel／sdist，源码／安装同ID、运行依赖及产品字节一致；所选旧元数据兼容检查。
- [x] 同冻结输入完整离线回归、原10秒恢复窗口与实际资源退出核对。
- [x] 同步当前能力／历史对比、交付入口与验收记录，仅暂存本轮文件本地提交；Git为最终提交依据。
