# Local 无模型异步 Tool 配置与安装后恢复

本批是第二阶段的有限异步扩展入口收口。已有 `GraphNode(tool=...)`、StaticWorkflowRuntime、ToolExecutor 和 Tool Action 足以执行 async 业务节点；实际缺口是 RuntimeProfile 不接受空 Provider 映射。只修改装配边界并补齐可安装示例，没有新增执行器、节点类型、后端或拓扑。

## 本批推荐本地制品

| 项目 | 值 |
| --- | --- |
| 私有版本 | `0.1.0a8+maintenance.54f45574ad74b3af` |
| wheel | `dist/model-free-tools-20261029/private-artifacts/relf_agent-0.1.0a8+maintenance.54f45574ad74b3af-py3-none-any.whl` |
| SHA256 | `3ca80c594b9d5e18946f4c016c41655754baee6284c8b96d05bc1107b9f64463` |
| 产品范围 | 451 文件；相对前批450文件仅改 RuntimeProfile、TemporalProfile、starter，增加一份应用模板资产 |

这是本地私有验证制品，不是新的 Alpha／公开版本或平台资格。此前 `349fff`／`709bc1` 私有包及原 a7／a8 两包、清单和历史失败全部保留；原制品不重建。各旧批次的“推荐”指其当时范围，本批是当前增量的唯一推荐包。既有项目不被生成器覆盖。

## 使用路径

安装此精确 wheel 后执行：

```sh
relf init my-tool-flow --template graph
cd my-tool-flow
python -m agent_app.tool_graph --order-id ORD-1 --command-id order-1
python -m agent_app.tool_graph --order-id ORD-1 --command-id order-1
python -m agent_app.tool_graph --order-id ORD-2 --command-id order-2 --submit-only
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine --format text inspect RUN_ID
relf --db .ralf/tool-graph.sqlite --factory agent_app.tool_runtime:create_engine resume RUN_ID
```

使用实际返回的 RUN_ID。输出的 model_actions=0、tool_actions=2、credits_spent=2 与固定 Manifest、Action 记录分别核对；credits 是执行额度，不是模型费用。订单／库存函数是异步只读夹具，不代表真实 API、业务写入或智能任务质量。完整配置、审批和排障见[工具节点指南](../../docs/managed-tools.md#安装后配置异步-tool-流程)。

## 保持的契约

- Local 的 providers 字段仍必填且必须是对象；只有显式 `{}` 表示无 Provider。JSON／TOML 不补隐式离线模型。实际 Agent 与混合图仍在接受 Run 前验证其有效 Provider。
- TemporalProfile 在任何工厂 I/O 前保留非空 Provider 要求；不恢复暂存的 Temporal 直接 Tool 节点探索。
- 原非空 Profile 的规范化、identity 和 Temporal 声明与上一已安装 SDK 完全相同。旧 SDK 明确拒绝新的空映射，不声称它能恢复新声明；原 Profile／适配器代码与数据仍需保留。
- 同步注册工厂仅登记 async handler，使用原 ProfiledEngine 和版本路由。真实异步客户端构造／关闭沿现有 abuild 和 owned／borrowed 契约，不伪装同步工厂或产生新执行权威。
- Tool 参数解析、Schema、授权、审批、稳定 Action／效果／attempt、预算预留、回执保存及未知效果核验均沿原路径。AgentLimits 仍是 Agent 范围；直接 Tool 节点消耗原 Workflow 额度。
- 原 graph 的 graph.json、runtime.toml、runtime.py 和 main 入口字节保持；只增加 README 说明和四份可编辑文件。另27种模板全部不变。

## 验证与失败保留

原始证据：`dist/model-free-tools-20261029/`。

- 基线74项通过。初始 RED 为7 failed／6 passed：六项 Local Profile 场景被原空映射校验拒绝，另一个场景确认缺少导出文件；Temporal拒绝／类型负例当时已经通过。
- 初步 GREEN 中两项误用不存在的 `to_dict` 方法，属于新测试夹具问题；改为通过公开 identity 对比，没有增加序列化 API。崩溃测试曾误将预期推进的 attempt 状态当作稳定身份，改为核对 attempt ID，保留原失败。
- 配置／Builder／Temporal声明／Tool恢复定向96项通过。新增必填字段用例和最终矩阵另验，不拼接为一次全量。
- 源码20模块 **339 passed，零失败／跳过，218.89秒**；`-W error`。包含串行／有限并发 Tool、审批重开与重复批准、未知写人工核验无重发、async取消迟到回执且无后继、真实进程在独立回执提交后退出、Profile 默认移动与缺失原版本等风险路径。
- 真实进程崩溃保留原同步场景，并增加 async handler；恢复核对原 Action、effect_key、digest、attempt IDs 和业务调用数1，不只检查最终输出相等。
- 隔离安装同一精确 wheel 的相同矩阵 **339 passed，零失败／跳过，189.31秒**；`-W error`，与源码测试 ID 逐项一致。测试夹具只复用已冻结安装环境，不另建同版本 Alpha；代码和断言不更换。
- 安装 CLI 在 checkout 外跑通文档7条命令，无 src／框架 PYTHONPATH 注入；重复提交返回同一 Run，submit-only 零消耗，inspect 与原工厂 resume 成功。
- 两个独立安装 SDK 比较：非空 Local／Temporal Profile identity 与 Temporal 声明逐项相同；上一 SDK 拒绝空映射，本批接受。

只读复核没有 Critical／Important 产品发现，额外独立31项通过；原图文件及四份新增资产已单独比较。Minor 为新示例错误 JSON 较简短：本批采用现有应用模式，文档明确用标准 factory CLI 的 inspect 查看 error／budget，不新增日志封装。真实 API／模型质量、任意 async 客户端及 Temporal 直接 Tool 扩展不在本批，安装验收由主任务独立完成。

环境为 macOS15.6.1 ARM64／Python3.12.7。文档首个 Tool 流程首条标准输出0.456秒、总耗时0.476秒；该输出是最终 JSON，不是模型首段。7个子进程累计 CPU user1.218秒／system0.373秒、最大峰值RSS47.22MiB；记录1次显式 inspect、1次 resume，内部轮询次数未测。不据此宣称性能改进、2CPU／2GB门槛、Linux或完整平台资格。

本批没有在线模型、Embedding 或远程数据／Temporal Service 调用。第一批已验收且未变的流与 Temporal 服务证据按其原制品复用，不借旧结果授予本包新的服务矩阵资格。

最终冻结核对：451产品文件与安装包逐项一致（仅私有版本后缀归一），其中前批447文件未改；LICENSE／NOTICE 字节一致。原 a7／a8 两包及清单、前两批私有 wheel 共8份保护文件哈希不变。339项源码与安装 ID 及20模块／崩溃夹具字节一致；28模板比较通过。Ruff、1487文件格式和 Git 空白检查通过，742个本地相对文档链接目标有效。未进行不相关的完整SDK／Linux／远程服务回归，不将历史成绩拼接成当前全矩阵。

## 交付终点与剩余

本批关闭“Local 有限 async 业务节点的配置、安装应用及原恢复入口”子门槛；第二阶段的默认连续应用与替换示例已在前批交付。任意循环、reducer、流式数据流、新后端及企业平台继续后置。

下一批进入第三阶段的固定最终配置任务评测：核对已有单 Agent、语义 RAG、Plan／Team 数据与可用模型资源，先冻结可重复的输入和业务／引用／恢复／耗时／用量评分，再执行；现有离线夹具不当作真实质量成绩。外部采用与对等框架比较独立验收。保持仅本地提交，不推送、远端 CI、部署或公开发布。
