# Temporal 增量流真实 Service 验收

日期：2026-10-29。持续目标仍为对比开源框架并优化 R01–R26，不因本批子集通过而缩小或关闭。上一轮两项观察／配置修复与隔离安装提供了实际进展；本批进一步关闭其原生 Agent 增量流的部分真实后端证据缺口。

## 选择与比较依据

[LangGraph 图 API](https://docs.langchain.com/oss/python/langgraph/graph-api)提供函数节点、共享状态和 reducer；[AgentScope Pipeline](https://doc.agentscope.io/tutorial/task_pipeline.html)提供顺序、fanout 与 MsgHub 等组合入口。它们说明 Relf 仍应继续完善通用节点、状态组合与使用便利性，不证明任一框架在相同业务上的恢复质量更优。

本批先复用已实现的统一增量流做真实 Service 验证，避免把 SDK 装配／模拟 Signal 直接计为分布式资格。未实现新的 NodeExecutor、共享状态、实时／多模态或部署平台；下一步相关能力仍在[完整清单](../../docs/remaining-work.md)。

## 实际范围

新增 `tests/temporal_stream_worker.py` 和 `tests/test_temporal_stream_service.py`，复用原 TemporalRuntime、注册 Worker、AgentRun、固定 Release、审批及 History 重放。**448个产品文件未变**，不增加运行依赖。工具为显式审批的只读 lookup；audit 文件只计夹具调用，不是业务写入，不证明任意外部效果恰好一次或真实模型质量。

原生 Agent 的三个实际场景：

1. 模型 Activity 被文件栅栏暂停时，通过原 Workflow 查询读到文本前缀；取消当前观察读取，业务保持运行。释放原响应后等待审批，工具尚未调用；重复批准返回原回执，最终两次模型／一次 lookup，execution credits 为3，unknown／reserved 为0。
2. 同一路径显式设置每 Attempt 两条 delta，实际记录有界文本与 gap；完整响应／工具回执仍成功，结束事实标注截断，不增加业务预算或重执行业务。
3. 模型完整响应与审批状态已进入 History 后，强制结束原 Worker 进程；从同一模块重新创建固定 Release 的 Worker，用新宿主 attach 原 RunRef，原事件保持。对同一命令重复批准并比对原回执，随后由新进程执行一次 lookup 与最后一次模型，首个模型不重复。实际PID／audit／返回码留档，原进程为-9、新进程最终为-15。

三个场景均拉取真实 History，使用原注册 Workflow 的 Replayer 重放，audit 不新增。这个进程恢复窗口发生在等待审批、没有在途工具时；不代替在途 Activity、接收／采纳之间、真实写效果／PostgreSQL Journal 或高级组合的故障矩阵。

## 先决条件及原失败

- 固定官方 Temporal CLI **1.9.1**，SHA-256 `33c298d41f6eefebf01a28a3511f444480e939e21d3518cb0c12a4abad467c4b`，与原已验证二进制一致；实际 Service **1.32.0**、SDK **1.34.0**。版本来源亦可核对[官方发行说明](https://github.com/temporalio/cli/releases/tag/v1.9.1)。
- SDK 下载参数 `1.9.1` 返回404；改为 `v1.9.1` 后下载持续异常缓慢，停止该自有下载。随后从同一官方 GitHub Release 取得资产并核对固定二进制哈希。404、慢速未完成文件及停止记录全部保留；没有替换旧服务／原数据。
- 首轮真实 Service **2 passed／1 failed**。重启夹具以 `-m` 运行，把 Provider 方法声明为 `__main__`，而客户端通过 `tests.temporal_stream_worker` 导入，触发原固定 Python 入口身份拒绝，审批等待超时。离线对比证实两份 Release 不同；仅修夹具的规范模块导入，并为审批等待增加终态失败诊断，未放松产品身份或增加期限。

## 最终验证

| 项目 | 实际结果 |
| --- | --- |
| 源码真实 Service | **3 passed**，JUnit 14.962秒；默认／限额流、观察取消、审批去重、进程重启后重复审批及三份History重放 |
| 目录外安装真实 Service | **3 passed**，JUnit 15.280秒；相同用例、夹具及期限；独立venv／site-packages，无src目录；同版本SDK及依赖的离线wheel安装、pip check和版本核对 |
| 复用精确私有包 | `0.1.0a8+maintenance.349fff3c5a4ef63b`，SHA-256 `25a05bee7d8a42d8e8319aa1aab090eb4d663452dec9af6ff717bf4192a0f01d`；产品未变，未重建私有包或原a8 |
| 无服务默认回归 | 受影响增量流／原状态／SDK模块 **57 passed／3 skipped**，3.26秒；三项跳过依赖真实地址的测试已在上面分别实际运行，不能把跳过计为通过 |
| 资源和历史 | 新建独立Service数据库／端口／测试队列，不启UI或时间跳跃，不读模型凭据；每轮服务finally关闭，测试创建的Worker进程退出，首轮失败及全部History／audit保留 |
| 静态及来源 | Ruff、1,479文件格式、Git空白检查通过；645个相对文件链接存在；源码／安装测试身份和文件字节一致；448个产品文件及原a7／a8四份包和两份manifest哈希保持 |

证据根目录 `dist/temporal-stream-service-20261029/`；源码与安装最终报告分别在 `source-final-repeat/`、`installed-final-repeat/`。初次成功阶段 `source-final/`／`installed-final/` 各3项通过仍保留；独立审查指出原计划还需覆盖“重启后重复审批”，补齐断言和所有PID退出记录后执行了上述最终复验，没有缩窄要求。

独立只读审查验证448个产品文件未变，最终新六份History均有两次相同审批结果；其独立离线重放 **6/6通过**，audit字节未变，无剩余发现。先前六份History的独立重放另行保留，不合并为最终测试数。首轮安装服务停止时出现一条Service的`Queue reader ... shard status unknown`日志，SDK shutdown已返回；不据此宣告生产停机／HA行为已验收。

## 支持边界

本批新增原生文本 Agent 的真实 Service 资格；Graph／Team／动态／嵌套增量流、运行中 Activity 被杀、响应／回执独立窗口、更换 Service 数据、旧 History 升级、长 History 容量、真实写／远程 Journal 和线上模型仍需各自验收。完整 R22、R09、M1、企业能力和对等框架质量保持开放。

前批全量沙箱诊断及其独立权限复验保持[原记录](2026-10-29-stream-observation-boundaries.md)，本批不补签未运行的全量 SDK 或 Linux／远端 CI。原 a8／a7 制品与 manifest 不改，当前 HEAD 保持 `19dcc60`，后续工作区未提交、推送或公开发布。
