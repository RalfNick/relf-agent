# Temporal 节点容量背压设计

日期：2026-11-09。基线 `4bb46fe`。用户已明确授权本轮容量背压、关闭诊断和交付入口的有限维护；沿已有持续执行偏好推进，不增加其他能力。

## 根因与选择

原 Tool Runtime 在取得 History 独占调用 claim 后才申请默认16槽 owner。满额拒绝因而进入业务失败采纳。原复现和失败保持在 `dist/node-executor-contract-20261109/known-capacity/`。

考虑过增加槽数、取得 claim 后在内存排队，以及原 History 托管容量等待。增加槽数仅移动阈值；claim 后排队会让取消后的排队工作仍可能启动，Worker丢失也没有持久等待证据。本批选择第三种：实际机械槽位先于原 History guard；只有明确的未启动容量拒绝可以进入 History timer，再请求同一逻辑 Action 的准入。

## 有限协议

- 默认节点使用独立 `NodeCapacityOwner`（16槽）和 `NodeNotificationOwner`（256槽）。独立类型只区分 full／duplicate／closed，不做业务调度或内存队列。原通用 Context owner 的固定 execute/wait/aclose 实现保持。
- 新 owner identity 的 kind 为 `workflow-node-capacity-owner`、behavior_version 为 `workflow-node-capacity-1`。仅该明确发布下的 executor 子 Run 使用新语义；旧普通、显式原 owner、Sandbox及Coding分支保持原规则。旧节点发布继续使用匹配的原包／Worker。
- 满槽且未持有该 Action、未关闭、原处理器尚未开始时，独立 owner 报 `NodeCapacityUnavailable`。不得把普通 memory_backend_error、duplicate、关闭或业务异常推导为容量拒绝。
- 新 Runtime 在 owner operation 内执行原 History guard，仍由该 guard 独占授权业务执行。容量拒绝响应带完整请求摘要、Scope、Action、Release、epoch和固定 transport ordinal；History核对原 intent 且无 claim 后才采纳。
- 原 Action／attempt／effect_key 和预算预留保持。每次容量准入使用不同的 History ordinal／transport Activity ID，并在 request digest 中固定 ordinal，拒绝旧 Activity 的迟到准入。最多64次明确拒绝，指数等待从0.1秒增长至1秒。
- 原 Native Workflow History 保存等待、ordinal、拒绝证据和计时窗口；不新增 Workflow／Activity 名称或独立数据库状态机。总窗口不超过原 schedule_to_close（activity_timeout×2+5秒），每个实际 Activity 仍不超过原 activity_timeout，后续只使用剩余总窗口。
- 等待由独立的 `workflow.sleep` Task 表示，再以无 timeout 的 `wait_condition` 等待该 timer 实际完成或原 Run 终态；实际完成后才允许推进容量重试。Drive／query 激活不重开 timer，不以查询更新后的时钟代替 timer 完成证据；到达原截止时间仍按原无启动 fence 结束，不派发新的业务。
- 仅新容量 executor 的 ACK Activity ID 采用原 Action 内持久递增的 `ack_ordinal`，不依赖 `len(event_log)`。重放必须生成相同 ACK ID；旧节点和普通分支继续保留原规则，不据新协议外推任意旧 History 兼容。
- 等待中的取消或到期只在 History 已证明无启动且固定 fence 后以0消耗结束。已有 claim、未知效果和普通失败仍沿原核验／停止规则，不能重做业务。
- 实际 handler、线程、结束通知与ACK责任保持各自原 owner；逻辑等待结束不替代真实工作或通知排空。关闭诊断只观察这些事实。

## 验收与边界

先保留真实 RED，再验证17节点及多个Run共享一个Worker时最多16个实际处理器，容量释放后每项一次效果；满额通知owner也需可恢复。覆盖容量与重复／关闭的区分、guard延迟、取消、预算、迟到请求、超时、ACK拖延和原对象关闭重试。

纯状态重建与真实 Temporal Service／Worker重启分别记录，不能以模拟授予Service资格。SDK源码与目录外准确私有安装包运行同一受影响集合，重建sdist核对产品内容，最后执行完整离线回归。保留所有原制品、失败和未选组合，其他工作区改动不进入本批提交。不推送、不触发远端CI、不公开发布。
