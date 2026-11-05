# Framework 接入边界维护计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 修复已有 Schema、Embedding 与聊天入口的接入失败，并更新真实差距说明。

**Architecture:** Local/Temporal 保持原执行权威。统一纯 Schema 校验；节点声明编译继续复用 Tool Action，不增加状态机。

**Tech Stack:** Python 3.11+、jsonschema/referencing、httpx、pytest。

**Spec:** [边界设计](../specs/2026-11-05-framework-boundaries-design.md)。

## Global Constraints

- 不增加后端、公共执行能力或依赖，不改变原期限。
- 保留原包和历史失败，不推送、触发远端 CI 或公开发布。
- 不访问模型密钥或调用真实付费服务；协议测试不作为真实质量成绩。

## Review Focus

- `$ref/$dynamicRef` 的本地资源根与 `$id` 空值、锚点、递归。
- 默认 Schema 解析不得触发文件或网络读取；普通业务 JSON 字面量不受重写。
- 错误前后原 Action/回执、审批和重复控制不重写。
- HTTP 异常转换不吞掉取消，不关闭借用客户端。
- 错误聊天输入不得提交 Run，后续合法查询继续使用同一会话。

## Tasks

### 1. 公共 Schema 边界

- [x] 先补真实公开验证入口的外部资源反例，记录 RED。
- [x] 新增内部 `schema_validation.is_valid(value, schema)`；使用项目已有无检索 Registry，引用错误转 ValidationError。
- [x] 替换普通 Tool、模型决策、Workflow 和直接 ToolSource 的动态校验；静态内置 Schema 与元 Schema 检查不机械重构。
- [x] 本地引用／不匹配／外部读取拒绝和相邻回归通过。

### 2. Node Schema 引用根

- [x] 真实 NodeExecutor 入口复现 input/config 本地引用失败。
- [x] 独立 Schema 嵌入时保持引用资源根，原声明与无引用 Manifest 保持。
- [x] 审批、重开、重复和非法输入回归通过。

### 3. Embedding 与聊天

- [x] 深嵌套 JSON、关闭借用客户端、聊天错误引号先 RED。
- [x] 最小异常转换；定向回归覆盖取消和错误后的后续合法命令。

### 4. 集成验收

- [x] 独立 review、相关源码／目录外安装回归，完成完整离线复验。
- [x] 更新对比清单、当前交付和能力状态，记录准确安装来源及未验证边界。
- [x] 仅本地提交，单次跳过钩子；原制品／未跟踪用户文件保持。
