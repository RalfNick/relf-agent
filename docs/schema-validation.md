# 固定 Schema 的校验边界

本文对应 2026-11-05 后的开发源码。原 a8 与历史私有包保持原字节；本轮安装验证和准确来源见[维护验收](../architecture/reviews/2026-11-05-framework-boundaries.md)。

Agent 最终输出、模型工具提案、注册工具、Workflow 输出、受管理节点，以及 HTTP／CLI／MCP ToolSource 的动态参数／结果校验，只能使用声明内的固定 Schema 资源。校验不会自动读取 `file://`、HTTP 或相对路径文件。

可以使用 `$defs`、本地 `$ref`／`$dynamicRef`，也可以引用同一声明内已有 `$id` 的嵌入资源。例如：

```python
schema = {
    "type": "object",
    "$defs": {"amount": {"type": "integer", "minimum": 0}},
    "properties": {"amount": {"$ref": "#/$defs/amount"}},
    "required": ["amount"],
    "additionalProperties": False,
}
```

这是共享校验边界的能力，不扩大模型协议或执行后端的 Schema 子集。Temporal 的纯历史检查、Responses 原生严格输出等入口仍可提前拒绝更广的关键字或非片段引用；具体组合以[模型矩阵](model-adapters.md)和[Temporal 指南](temporal-execution.md)为准。

未解析引用或超出解释器支持深度的递归返回框架 `ValidationError`；普通不匹配保持各入口原错误类型。Schema 中 `const`、`default` 或 `examples` 里的业务 JSON 不会当成 Schema 递归改写。需要外部 Schema 的应用应在发布前自行取得、检查并嵌入固定资源，同时更新组件版本；运行时不提供隐式下载或可变远端缓存。

## 受管理节点的独立引用根

`NodeExecutorSpec.input_schema` 与 `config_schema` 各有独立的 Schema 根。框架编译成原 Tool 参数包装时，仅为含实际引用且没有有效资源 ID 的嵌入副本增加确定性层级 URI；原 Spec 不变。该 URI 仅标识本地固定资源，不触发网络请求。

已有有效 `$id` 保持；两个资源经解析后同一 ID 对应不同定义时，注册提前拒绝。完全相同资源可共享。不能用 input 的 `$defs` 去解释 config 的局部 `#/` 引用，反之亦然。

## 原任务与代码升级

无引用节点的普通 Tool／Registry Manifest 已针对旧实现核对保持。含引用的节点包装修复会改变对应 Tool Manifest；typed Python 工具的参数校验代码变化，也会按原 `bridge_code` 规则改变实现身份。这两类不能视为透明的原 Run 跨包迁移。

保留原安装包、应用代码、配置和数据处理已接受的任务；新逻辑使用新的发布和请求身份。遇到 `DefinitionMismatch` 时按[恢复指南](recovery-guide.md)恢复匹配原实现，不修改原回执、移除指纹检查或自动重做未知写效果。本轮没有改变 Local／Temporal 执行权威、审批、预算或显式取消语义。
