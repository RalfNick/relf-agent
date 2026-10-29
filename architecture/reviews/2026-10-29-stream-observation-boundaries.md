# 增量流观察与配置边界维护

日期：2026-10-29。继续优化[前批统一增量流](2026-10-29-agent-stream-updates.md)，不增加新执行能力、依赖、Schema 或执行权威。HEAD 保持本地 `19dcc60`；其后的增量流与本轮修复仍保留工作区，不提交、推送或公开发布。原 a8／a7 制品、manifest 和前批失败／私有验证包均保留。

## 发现与处理

1. **P2：并发读取拒绝误关已有观察者。** 同一 `AgentStreamSubscription` 有一个正在等待的 `anext()` 时，第二个读取应由原 `RunEventSubscription` 拒绝。投影层原先把读取和投影放在同一个 `try` 中，收到该拒绝后调用 `aclose()`，取消第一位观察者的实际读取。新增真实订阅反例 **1 failed**；将原读取移到投影错误处理之外，读取准入、取消、清理继续由原订阅负责。只有投影错误由投影层关闭观察，最后有效游标保持。
2. **P3：超大整数配置逸出公共错误类型。** `StreamUpdatePolicy(publish_timeout=±10**400)` 在范围校验前被转换为浮点进行有限性检查，抛 `OverflowError`。新增反例 **2 failed／8 passed**；改为先执行原范围检查，再检查有限性。原范围、默认值和 Release 身份不变，统一返回 `ValidationError`。
3. **取消清理回归。** 新增源调用在迭代器 `aclose()` 等待期间被取消的测试：传播真实取消、保留清理句柄、拒绝新的派发、活动调用时拒绝清理重试，排空后显式重试且重复清理幂等。该项验证既有行为，没有把观察关闭变成业务取消或关闭借用 Provider。

相对前批已验证的 448 个产品文件，仅 `stream_updates.py` 两处代码变更；不是再次改动 Local／Temporal 状态推进。独立只读复核 **65 passed**，使用 `-W error`；额外验证跨事件循环读取拒绝、有效前缀后坏记录保留游标，以及 `from_identity` 的正负超大整数错误。无新增可操作发现，未读取凭据或启动真实外部服务。

## 扩大检查的环境失败记录

本轮尝试默认全量收集，共 15,598 个用例。在当前沙箱中，HTTP 夹具监听 `127.0.0.1` 直接被 `PermissionError` 拒绝，Coding 监督进程／本地 socket 用例也连续失败。主代理用 SIGINT 停止该轮诊断，pytest 执行清理并生成报告；**1,947 passed／49 failed／42 skipped／6 errors**，351.589 秒，退出码2。该轮不是完整验收通过，不删除、不筛改报告。

全部55条失败／错误记录的用例名称、消息和堆栈保存在 `dist/stream-boundaries-20261029/final/source-full-failures.json`，原始报告为同目录 `source-full.xml`／`source-full.log`。涉及 A2A HTTP／starter、Artifact、Coding CREATE／Runner／容量／预检／transport 模块。

独立沙箱 HTTP 单项复现相同权限错误；允许本机监听后，原四个 HTTP 模块 **9 passed**，36.06 秒。Artifact 的该次失败为两个未关闭 socket 在测试期间延迟回收引起的 `PytestUnraisableExceptionWarning`，未出现业务断言失败；单项及完整模块另行重跑 **1 passed／26 passed**。

随后将全部55条失败／错误记录去重为52个原用例，在清空凭据环境、允许本机 loopback／Unix socket 的独立诊断中复验，**52 passed**，JUnit 113.352 秒，零失败／错误／跳过。没有修改这些测试、期限或产品协议；52条通过不补签中止轮未执行的其他用例，不表示完整 SDK 或全部宿主时序问题已关闭。HTTP／合成 Coding 均为本机测试夹具，未调用真实模型／业务服务。

## 最终验证

| 项目 | 实际结果 |
| --- | --- |
| 所选85模块源码回归 | **1,379 passed**，JUnit 113.064 秒，`-W error`，零失败／错误／跳过；66个核心模块、19个 Temporal 离线／SDK 模块 |
| 所选66模块目录外安装 | **1,158 passed**，`-W error`，零失败／错误／跳过；与源码对应核心用例完整身份核对 |
| 私有验证包 | `0.1.0a8+maintenance.349fff3c5a4ef63b`；wheel SHA-256 `25a05bee7d8a42d8e8319aa1aab090eb4d663452dec9af6ff717bf4192a0f01d`；448个产品文件、LICENSE／NOTICE、独立venv／site-packages导入、模块／METADATA版本和pip check核对 |
| 安装方式 | 原样复制测试／断言和示例，检查目录不含src。仅异步starter的installed_wheel资源夹具使用这份精确私有包的Python／CLI，不另建源码包；原a8不重建 |
| 静态和来源 | Ruff、1,477文件格式和Git空白检查；源码／测试、原a7／a8包与manifest哈希及文档相对文件链接核对 |

本轮证据在 `dist/stream-boundaries-20261029/`，最终所选回归、私有包和核对摘要在其 `final/`；前批 `dist/stream-updates-20261029/` 的输入、失败及私有包全部保留。独立只读review核对了产品范围、65项测试及文档口径；所选模块范围已按其建议直接写入上表。

## 保持的限制

本批不验证新功能的真实 Temporal Service／History 故障窗口、线上模型质量、Linux／远端 CI 或公开发行。Local／Temporal、原 RunRef／Scope／Release、业务取消、审批、回执／未知效果恢复、预算与资源所有权保持原协议。不得将一次独立诊断或所选测试通过拼接为全量 SDK、完整 R22／R09、M1 或企业可用资格。
