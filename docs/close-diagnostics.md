# 关闭未完成的诊断与重试

2026-11-09 维护源码为 `CloseIncomplete` 增加只读 `diagnostics`，用于说明原关闭责任当前阻塞的位置。准确候选 `0.1.0a8+capacity.c5a29d8fa601a9ec` 的源码／目录外安装各884项、真实Service同5个ID各5/5及运行依赖16条检查通过，sdist重建464产品一致；完整源码回归15685通过／913条件跳过、零失败／错误，本轮有限维护已验收，见[当前交付](current-delivery.md)及[本轮记录](../architecture/reviews/2026-11-09-temporal-capacity-close.md)。原推荐组合、a8 和此前私有验证包不包含本批诊断增量；它们继续使用原关闭接口。

原 `CloseIncomplete.report`、错误码和消息保持。诊断只投影已知关闭事实，不驱动 Run、取消业务、重发工具、关闭资源或释放租约。调用方取消关闭等待仍传播 `CancelledError`，不能据此认定实际清理已停止。

## 读取诊断

```python
from relf_agent import CloseIncomplete

try:
    await runtime.aclose()
except CloseIncomplete as error:
    print(error.diagnostics)
    # 保留 runtime；修复实际阻塞原因后，在原创建循环重试同一实例。
```

`diagnostics` 返回独立的有限 JSON 副本，修改这份副本不会改变异常或关闭过程。形状为：

```json
{
  "schema_version": 1,
  "state": "incomplete",
  "authority": "temporal",
  "stage": "handler_drain",
  "ownership": "owned",
  "blockers": [{"kind": "handler", "count": 1}],
  "retry_action": "retain_original_instance_and_retry_close"
}
```

上例表示原 owner 仍托管一个操作而阻塞排空，不是所有关闭错误的固定返回值。`handler` 计数代表原 owner 托管操作；新节点的操作可能仍在等待原 History 准入，不能据此判断业务处理器已启动、请求已派发或效果已经存在。业务派发仍以原 History／效果事实为准。字段约束如下：

| 字段 | 含义 |
| --- | --- |
| `authority` | 已知的 `local`／`temporal`，无法确认时为 `unknown` |
| `stage` | `run_drain`、`rpc_drain`、`construction`、`execution_drain`、`handler_drain`、`end_ack`、`worker_start`、`worker_stop`、`authority_close`、`resource_close`；未接入来源为 `unknown` |
| `ownership` | 原关闭对象的 `owned`／`borrowed`／`mixed`，无法确认时为 `unknown`；Temporal Facade 的 `owned` 指其本地 Engine Facade，不表示它拥有借用的 SDK Client 或 Worker |
| `blockers` | 已确认阻塞项的固定类型与实际非负整数计数；类型为 `run`、`rpc`、`construction`、`handler`、`thread`、`end_ack`、`worker`、`resource`；计数上限为 `2**63-1` |
| `retry_action` | 固定为 `retain_original_instance_and_retry_close`，提醒保留原实例和关闭责任 |

未知计数不会写成 0；布尔值、非法或超过上限的计数省略。空的 `blockers` 只表示没有可安全呈现的计数，不证明没有后台工作。诊断不回显原 report 正文、Scope、Run／Action 标识、路径、业务参数或原始异常；仍须在可信宿主侧结合原回执及运行记录排障。

## 按原责任重试

- **处理器或线程未结束：** 等待真实工作退出，保留其客户端、执行权和效果日志，再对原实例重试关闭。Run 终态或取消回执不代替实际停止证据。
- **结束通知／ACK 未排空：** 修复原通知或日志路径，继续等待原结束事实；不要重新执行已发送的业务操作。
- **Worker、构造或 RPC 尚在途：** 保留原被托管工作。取消外层等待不会转移其责任，也不授权提前释放共享资源。
- **资源关闭失败：** 修复该原资源的关闭条件，然后在原创建事件循环重试。已完成关闭的资源按原生命周期规则保持完成，较早依赖继续保留。

```python
# blocker 已实际解除，且仍位于创建 runtime 的同一事件循环。
await runtime.aclose()
```

Assembly 的外层排空若只能确认整段执行仍在途，会使用 `execution_drain`；只有内层已确认处理器或 ACK 阻塞时才给出更具体阶段。CLI 对顶层 `CloseIncomplete`，以及直接 `__cause__` 精确为 `CloseIncomplete` 的原 `RuntimeBuildError` 追加同一安全 `diagnostics`。后者保留外层原错误码、消息和 cleanup 责任，不继续遍历其他异常链。其他错误类型和格式保持，原生 `ConnectionError` 等不会被本批泛化包装。未接入的旧关闭来源仍可抛相同异常，其诊断保留 `unknown`，不能把缺少详细投影当作关闭成功。

Local 的原等待／取消语义见[Agent API](agent-api.md)，Temporal 的原关闭托管见[Temporal Agent API](temporal-agent-api.md)和[Profile 生命周期](temporal-profiles.md#关闭与恢复责任)，工厂资源所有权见[异步装配](async-assembly.md#关闭取消与错误)。本批不添加新的 Runtime 查询入口、关闭策略、执行权威或自动业务恢复行为。
