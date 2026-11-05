# Temporal Managed Nodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在原 History／Tool Action 协议内交付 Temporal 无状态 executor 图及恢复证据。

**Architecture:** 父编排托管私有单工具子 Run；纯 helper 复用 native 状态和原 Activity，注册与实际生命周期归原 Runtime／Assembly。

**Tech Stack:** Python 3.11+、Temporal SDK、既有 NodeExecutorRegistry、PostgreSQL EffectJournal、pytest。

**Spec:** [设计](../specs/2026-11-05-temporal-managed-nodes-design.md)。

## Global Constraints

- 无新 Workflow／Activity 名，无虚假 Provider／LocalEngine／第三套调度器。
- 原期限、原制品／失败保留；无节点默认 Manifest 不增加节点字段。旧普通 History 按所选记录验证，不笼统保证所有旧 History 透明回放；旧 Coding 固定纯实现指纹，需原包／匹配 Worker。
- 本地提交单次跳过钩子，不推送／远端CI／公开发布。
- 真实本机服务独立资源，只清理自有进程／容器；不访问模型密钥。

## Review Focus

- 伪造 node_request／父身份、普通 Agent 私有工具越权。
- 原回执与真实结束分离，未知效果不得重写或提前释放 cap。
- 已发生写后 Schema 拒绝仍保存效果与额度。
- 无标记旧 History 和未选 Session／Coding／部署组合的明确边界。
- 构造／等待取消后原 owned／borrowed 资源关闭可重试。

## 1. History 权威与父子投影

- [x] 先补纯状态及实际 SDK 入口 RED，固定 `workflow_node_protocol=1`、`workflow_nodes`、私有 `kind=executor` 与原 `node_request`。
- [x] 实现 temporal_node_protocol/state 纯 helper；修改原 state/parent/workflow 的 opt-in 分支，普通路径不变。
- [x] 覆盖审批、预算、ACK／end、unknown／cancel、输出和父子拒绝／所选兼容。

## 2. Runtime 与 Activity

- [x] RED 后加入 workflow_executors 借用注册、固定发布和默认原 ToolExecutionOwner。
- [x] execute／reconcile／ack 私有路由复用原 Journal／授权／停止链路；不把私有工具放入公共 Registry。
- [x] 证据、漂移、实际调用关闭及原默认发布回归通过。

## 3. 装配与默认使用

- [x] Profile／JSON／TOML 与 identity 默认组件先 RED，再允许仅节点空 Provider。
- [x] 复用原工厂预检、资源台账与 Assembly 关闭；补正确能力查询与非法组合拒绝。
- [x] SDK 默认与第三方客户端工厂替换均有可运行例子。

## 4. Service 与交付

- [x] 原本机 Temporal 二进制及缓存 PG 镜像构建独立测试服务，不下载新模型或容器。
- [x] 固定真实故障矩阵、Worker 重启与原 namespace History replay；源码和准确安装各自验证，不拼接资格。
- [x] 全轮执行与失败分类定向闭环、准确 wheel／sdist 和运行依赖首用、独立 review、能力文档／验收与原制品哈希核对。原全轮15479通过／1失败／908跳过；唯一旧 ACK 夹具缺少 `_manifest`，仅补夹具后源码／准确安装原模块各8项通过。459个产品文件不变，原全轮失败保留，未再次运行整轮，也不称单轮全绿；详见[验收记录](../../../architecture/reviews/2026-11-05-temporal-managed-nodes.md)。

交付约束：仅本地提交，单次跳过钩子，不推送、远端 CI 或公开发布；实际提交状态以 Git 为准。
