# Temporal Node Capacity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收口默认Temporal节点满槽导致业务失败的问题，并保持原准入、预算及恢复责任。

**Architecture:** 独立机械owner区分明确容量拒绝；原Native History持有有界timer、同Action预算和准入fence。关闭诊断与交付入口是并行有限子任务，不增加执行权威。

**Tech Stack:** Python 3.11+、现有Temporal SDK／纯History状态、pytest、已有离线构建依赖。

**Spec:** [设计](../specs/2026-11-09-temporal-node-capacity-design.md)。关闭子任务见同日close-diagnostics设计／计划。

## Global Constraints

- 默认16执行槽、256通知槽不增大；最多64次容量拒绝，0.1秒指数增长、上限1秒，使用原schedule_to_close总窗口。
- 原通用Context owner固定方法、普通／显式原owner分支、Action／attempt／effect_key／预算语义保持。
- 仅明确新节点owner发布启用；未知、重复、关闭不得自动重试。旧发布继续保留原包／Worker。
- 原制品／失败／受保护审查／其他网站工作区改动保留。最终单次跳钩子本地提交，不推送／公开发布。

## Review Focus

- 重复调用或handler已运行时的拒绝不能冒充未派发容量不足。
- 容量回应、迟到准入和新ordinal竞争时，原History只能授予一个真实业务调用。
- timer期间取消／deadline／Worker重启，预算、等待和无启动证明不能丢失。
- handler结束与ACK未排空分别保留责任；关闭诊断不推进业务或暴露原异常正文。
- 普通旧发布与明确新节点发布分开比较，不以默认新行为宣称任意旧History可透明迁移。

## 1. 独立容量owner

- [x] 新建temporal_node_capacity_owner.py与test_temporal_node_capacity_owner.py；缺模块真实RED。
- [x] 实现NodeCapacityUnavailable、NodeCapacityOwner和NodeNotificationOwner；只转换自身准确full拒绝。
- [x] 验证duplicate／closed／非法输入不转容量、原Context固定实现不变、处理器和通知责任保留。

## 2. Runtime及原History集成

- [x] 新建temporal_node_capacity.py纯规则与定向测试；覆盖完整proof、同Action预算、ordinal fence、重复回应、取消和超时RED。
- [x] temporal_activities／temporal_tool_execution发布新默认owner及固定通知描述；temporal_tool_execution_runtime仅新节点分支在获得槽位后调用原guard。
- [x] temporal_tool_execution_state／temporal_state／temporal_node_state集成原intent和同预算重试，不重新reserve。
- [x] temporal_workflow使用原History计时窗口和唯一transport ID；不新增Workflow／Activity类型。
- [x] 原17节点反例、多个Run、迟到请求、guard延迟、等待取消和原关闭重试通过。

## 3. 恢复与交付

- [x] 覆盖timer持久重建、Worker重启、未知已claim和实际ACK拖延的恢复；真实服务与离线成绩分开。
- [x] 与关闭诊断子任务共同独立review，修复范围内问题并保留RED。
- [x] 固定源码／输入／旧制品SHA，源码受影响集合与准确隔离wheel同ID通过，运行依赖及sdist产品一致。
- [x] 完整离线回归15685通过／913条件跳过、零失败／错误；原16490个测试ID全保留，本批884项及原五个10秒恢复窗口全过，首轮部分失败保持。
- [x] 同步交付入口、能力与验收记录，明确本批范围并显式排除他人工作区文件；本地提交以Git记录为准，未推送或公开发布。
