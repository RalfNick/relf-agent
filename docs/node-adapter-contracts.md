# 自定义异步节点检查

2026-11-09 源码新增 `node-executor`／contract version `1`／profile `core`。它复用既有 AdapterContractSuite，用真实 LocalEngine、NodeExecutorRegistry、SQLite Run／Action 记录核对组件接入；不添加执行后端、重试或调度权威。原 a8、推荐组合和此前私有包不包含本批实现；准确验证范围见[当前交付](current-delivery.md)。源码／准确安装各815项、运行依赖14条检查通过，完整源码回归15582通过／908条件跳过、零失败／错误，见[验收记录](../architecture/reviews/2026-11-09-node-executor-contract.md)。不据此认证 Temporal、写幂等、真实业务质量或独立采用。

## 从安装后的 CLI 开始

```sh
# 不访问模型、数据库或 fixture；返回 not_run／未验证。
relf-check-adapter --role node-executor

# 明确选择独立 SQLite 参考；运行真实 Local 图与清理检查。
relf-check-adapter --role node-executor --offline

# 证据目录须不存在；报告仅含固定计数、摘要和相对证据路径。
relf-check-adapter --role node-executor --offline --evidence-dir /ABS/new-node-evidence
```

默认仍是原 knowledge-retriever 角色，不自动选择节点、凭据或远程端点。`--offline` 验证的是包内独立参考，不能证明你的业务组件已通过。相同证据目录不能覆盖重用。

## 固定检查项

| ID | 实际检查 |
| --- | --- |
| N01 | 原结构化 identity、异步 execute 端口、注册及脱离源对象的描述 |
| N02 | 完整有限 JSON／独立 config、null／false／0等输出，原已保存结果与结算 |
| N03／N04 | 输入／配置 Schema 在调用处理器前拒绝 |
| N05 | 输出 Schema 失败保留真实回执与消费，不重调组件 |
| N06／N07 | 原身份／方法漂移后拒绝，替换处理器未执行 |
| N08 | 处理器异常保留原 unknown 状态和额度，不把异常当成功 |
| N09 | 读取型节点审批、预算拒绝、重复命令和 SQLite 关闭重开 |
| N10 | 真实 LocalEngine.drive 调用方取消、实际处理器退出、关闭拒绝与原对象重试，借用资源不被 Engine 关闭 |

Suite 的 probe 注册固定为只读、cost=2；缺少某项所需控制端口时为 `not_verified`，不是通过。N08 的 `waiting_reconciliation` 是原引擎对未知结果的事实，不是测试框架替业务确认失败或成功。N09 保留原“先审批，再预留额度”的执行顺序。

这些检查验证 fixture 配置下的接口和消费链路，并非要求所有业务节点接受任意 JSON。只接受特定业务输入的节点应使用隔离测试服务和适当测试配置；不能把一个测试 shim／参考组件的成绩当成原业务逻辑、Schema 或写效果的认证。

## 替换成自己的组件

节点不需要继承框架类，实现 `identity` 和 `async execute(input, config, context)` 即可。fixture 把可控制的测试供应端接到 Suite，提供管理回调；它不返回 passed／failed，不创建 Run，也不提供 Action 回执。

```python
from relf_agent import AdapterContractSuite, NodeContractResource, NodeContractSession

class MyFixture:
    async def prepare(self, case_id, workspace):
        client = await open_disposable_test_client(workspace)
        node = MyNode(client)
        return NodeContractSession(
            component=node,
            resources=(NodeContractResource(client, asynchronous=True),),
            configure=client.configure_test_response,
            inject_fault=client.inject_test_fault,
            pause=client.pause_test_call,
            audit=client.read_test_counts,
            reopen=client.reconnect_same_source,
        )

suite = AdapterContractSuite(role="node-executor")
try:
    report = await suite.run(MyFixture())
finally:
    await suite.aclose()
```

`prepare` 可以同步或异步；每项独立 workspace，最多16个明确 owned 资源。没有列入 resources 的组件／客户端为 borrowed，不由 Suite 隐式关闭；调用者负责其生命周期。

- `configure('output', {'result': finite_json})`：配置真实供应端输出；不能返回 ModelResponse、Run 回执或验收结论。
- `inject_fault(kind)`：支持 identity-drift／method-drift／handler-error／reset。
- `pause('execute')`：返回 `NodeContractPause(wait_entered, release)`；实际处理器必须进入暂停，不能用立即完成的假 hook 通过 N10。
- `audit()`：只返回 execute_calls／reconcile_calls／close_calls 的非负整数累计值；不能返回业务正文、密钥或 verdict。
- `reopen()`：原 Engine 关闭后重连同一组件／数据源，identity 和执行计数保持。close_calls 可增加。

`NodeContractSession` docstring 中的 `configure reset` 是可选辅助能力，本 Suite 不调用或认证它。除 audit／pause 外，管理回调应完成并返回 None。管理端口不是新的执行后端；它们仅为可处置测试环境安排真实数据和故障。共享角色的状态码、报告格式和原角色摘要保持。

## 可编辑示例与清理

[独立示例](../examples/node_executor_contract.py)定义普通 Python 组件和 fixture，未继承 SDK 的节点实现，也未复用内置参考组件。安装当前 SDK 后，在 checkout 或 sdist 示例目录执行：

```sh
python examples/node_executor_contract.py --evidence-dir /ABS/new-example-evidence
```

示例组件是内存测试供应端；N09 验证原 Engine 的 SQLite 恢复，不能据此推导该供应端支持跨进程持久业务数据。内置离线参考另外使用独立 SQLite 记录真实输入、config 和调用计数；这些应用观察不会成为 Run 的执行权威。

N10 使用低层 LocalEngine.drive：取消该调用方沿既有实现请求业务 Run 取消，同时实际处理器可能仍运行；该检查不把低层行为冒充高层 AgentRun.wait 的只读观察取消。高层等待和事件订阅的取消边界保持原契约。

清理失败保留原 Suite 和工作目录，在创建它的事件循环上重试 `await suite.aclose()`。取消观察也不授权提前关闭实际处理器使用中的客户端；无法确认清理完成时报告失败／pending，不释放原责任。报告只给固定错误码，原始业务异常不进入报告。CLI 无法替代应用持续保留失败对象的责任。

失败时先按 case ID／label 核对测试配置和管理端口。异步管理回调应 `await` 原工作后返回 None，不能直接返回活动 Task；跨事件循环的未完成 Future 不提供正常执行兼容，只会保留清理责任，实际完成后再重试原 cleanup。保留证据时，各 case 的原 SQLite 数据可在本机辅助排障；不要把私有业务数据上传为公共报告。检测器还会区分 JSON false 与数字0，不用 Python 的宽松相等替代业务数据校验。

本批不关闭完整 R25。下一组合、远程服务、写核验、Temporal 或真实模型成绩都需要单独证据；参见[能力清单](remaining-work.md)和[通用节点用法](managed-async-nodes.md)。
