# 第一批：生命周期、事件与模型／工具增量流收口

按用户最新目标，本批只冻结已有生命周期修复、持久事件订阅及模型文本／显式异步工具 JSON 增量，不新增后端、拓扑、适配器或企业能力。

## 交付与唯一推荐本地制品

`subscribe_events()` 读取原持久事件，`stream_updates()` 提供带来源的类型化展示。显式 `StreamUpdatePolicy` 默认关闭；`StreamedModelProvider` 仅在 EOF 验证完整响应后交还原执行者。展示增量、持久事件、模型响应、工具回执和最终业务结果保持独立；前缀不能生成工具提案，进度不能确认效果。

| 固定项 | 值 |
| --- | --- |
| 安装版本 | `0.1.0a8+maintenance.349fff3c5a4ef63b` |
| wheel | `dist/stream-boundaries-20261029/final/private-artifacts/relf_agent-0.1.0a8+maintenance.349fff3c5a4ef63b-py3-none-any.whl` |
| SHA256 | `25a05bee7d8a42d8e8319aa1aab090eb4d663452dec9af6ff717bf4192a0f01d` |
| 产品 | 448 文件，源码摘要 `349fff3c5a4ef63b1f2b3d87d63e3e2b37aeb1b77949a2a955e59ffd65e9c566` |

复用字节匹配的精确私有包，不重建原 Alpha。它是本地交付推荐，未公开发布。源码 Alpha 基版本保留原值，安装制品的元数据和 `__version__` 都含完整私有后缀；原 `0.1.0a8` 包不包含本批 API。旧包、失败与平台记录各自保留。

```sh
python -m venv /tmp/relf-stream-app
/tmp/relf-stream-app/bin/python -m pip install dist/stream-boundaries-20261029/final/private-artifacts/relf_agent-0.1.0a8+maintenance.349fff3c5a4ef63b-py3-none-any.whl
cp examples/stream_updates.py /tmp/relf-stream-app/app.py
cd /tmp/relf-stream-app
bin/python app.py --db runs.sqlite
bin/python app.py --db runs.sqlite
```

第二次使用原命令读取原事件和结果，不产生新的模型或业务调用。真实模型须显式替换 Provider；离线例子不证明模型任务质量。

## 风险相关门槛

| 门槛 | 实际范围 |
| --- | --- |
| 慢消费者 | Local 消费一条后停止读取，Run 独立完成；原游标逐页重连无遗漏／重复，gap 保留 |
| 观察取消 | Local 和真实 Temporal 前缀阶段取消观察，不取消业务或关闭借用 Worker |
| 审批／重启 | SQLite 关闭重开；Temporal 等待审批时杀 Worker，原 RunRef 续接并重复审批，handler 只调用一次 |
| 未知效果 | Local 接收响应／回执窗口回归；真实 Temporal 原生 Agent＋ToolExecutionOwner 丢失只读合成回执，展示不解除 unknown 额度，查询恢复且不重执行 |
| 关闭重试 | EOF 完整响应保留；失败／取消的迭代器关闭保留清理对象并能重试，不关闭借用 Provider |
| 默认兼容 | 只读审查对照 HEAD：关闭新策略时 Manifest、Agent 工具提案、派发参数和事件相同；固定历史任务仍须原制品 |
| 隔离安装 | 精确 wheel、目录外 site-packages、相同测试 ID／字节，无 src 注入 |

最终原始数据位于 `dist/stream-final-20261029/`。较宽的未受影响证据复用：源码 1379／安装 1158 项，socket 权限隔离复验 52 项，详见[观察边界记录](2026-10-29-stream-observation-boundaries.md)；不等于完整 SDK／平台资格。

最终补强验收：风险相关 15 模块源码 **156 passed（7.22s）**／目录外安装 **156 passed（9.40s）**，测试 ID 和字节相同；真实 Temporal **4 passed（19.41s）／安装 4 passed（20.58s）**，均 `-W error`，无跳过。CLI 1.9.1／Server 1.32.0／SDK 1.34.0，独立数据库、原 namespace、非时间跳跃，全部自建服务和 Worker 已关闭。未知窗口明确核对 unknown 额度、单次 handler、展示不确认效果、查询后原 Run 成功与实际 quiescent；保存的 History 按原 namespace 重放。

夹具文件最终格式冻结后，`source-frozen`／`installed-frozen` 同四项再次 **4 passed（19.69s）／4 passed（20.66s）**；源码与安装夹具字节一致。前述通过记录和格式检查首试失败保留，产品字节没有变化。

只读独立审查未发现未关闭的重要问题，并复核 448 文件与精确私有 wheel 一致（仅构建版本后缀差异）。本批不是性能 benchmark，以上耗时只描述固定验收任务；未声称真实模型质量、跨框架优势或新平台资格。

## 保留记录与范围

最终脚本首试 CLI 路径错误，服务未启动，原记录保留。探索重放漏传 namespace，SDK 正确拒绝结束证明；补传 `namespace=client.namespace` 后同一 History 重放通过。这是夹具问题，没有放松身份检查，也不宣称原调度存在产品不确定性。

第二批的活动 ID 调整、直接 Tool 节点及测试共 15 文件保存于 `dist/temporal-tool-nodes-20261029/deferred-snapshot/`（原基线、完整草稿、补丁与 SHA 清单），已从本批源码移出，不计为支持。探索通过与失败均保留。Coding 等原实现指纹没有放松；新包不接管任意旧固定任务。

支持有证据的 Local 增量接口及本批原生文本 Agent 的 Temporal 组合。高级组合完整增量／辅助阶段、在途 Activity 崩溃、独立响应／回执接收窗口、真实写和 PostgreSQL Journal 仍未验收。推理／参数流、多模态、逐记录 Workflow、跨宿主、HA 和完整企业治理后置。展示限额不替代历史保留治理。

下一批先降低已有 Agent／Runtime／Profile 接入成本，再单独审查有限异步节点草稿；不自动增加循环、reducer 或复杂共享状态。
