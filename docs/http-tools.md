# 固定目标 HTTP JSON 工具

`HTTPToolSource` 通过原 ToolSource／ToolRegistry 接入可信业务 HTTP 接口。
宿主固定 URL、POST／GET、Schema、版本和显式头；模型只提供 JSON 参数。
授权、审批、effect key、未知效果与恢复仍由原 Engine／Temporal History 管理。

## SDK 注入

```python
from relf_agent import (
    HTTPToolSource,
    ToolDescriptor,
    ToolPolicy,
    ToolRegistry,
    register_tool_source,
)

registry = ToolRegistry()
source = HTTPToolSource(
    ToolDescriptor("lookup", "Lookup", {"type": "object"}),
    "https://your-business.example/lookup",
    version="lookup-v1",
    headers={},
)
await register_tool_source(
    registry,
    source,
    policies={"lookup": ToolPolicy("1", effect="read_only", requires_approval=False)},
)
# 应用拥有独立 Source；直接注册只借用它。
# 应用退出时先等待执行，再关闭：
await source.aclose()
```

API 不接受运行输入提供 URL、方法或头，不跟随重定向，不自动重试；默认不读取
环境代理、Cookie 或凭据。HTTP(S) URL 不允许凭据、查询、fragment、空白／控制字符。
显式 headers 被复制，identity 仅保存头名和值摘要；不将秘密放入 URL 或字面 Profile。
原实际端点／DNS／服务实现及凭据权限仍由宿主负责。

默认方法为 `POST`，原 identity、canonical JSON 请求正文和传输调用保持兼容。
默认输入和响应正文各限1 MiB，可设1–16777216字节。输入是 canonical UTF-8 JSON，
响应必须为HTTP 2xx、一个有限 UTF-8 JSON 值，并符合可选输出Schema；重复键、
孤立surrogate、非有限数字、无效／过量正文均拒绝。错误不携带URI、头、正文或
服务诊断。POST的Content-Type固定JSON，Accept-Encoding固定identity；压缩响应拒绝，
避免无界解压。显式头禁止Host／Content-Length／Transfer-Encoding／Content-Type／
Accept-Encoding及大小写重复字段。流式业务响应、凭据代理另行支持。

## 固定 GET 查询

显式设置 `method="GET"`，参数默认采用 argument 名称。可用
`query_parameters` 固定 argument 名到目标参数名的一一映射：

```python
source = HTTPToolSource(
    ToolDescriptor("search", "Search records", {"type": "object"}),
    "https://your-business.example/search",
    version="search-v1",
    method="GET",
    query_parameters={"query": "q", "tags": "tag", "active": "enabled"},
)
# {"tags": ["a&b", "中文"], "query": "a b", "active": True}
# 实际查询：enabled=true&q=a+b&tag=a%26b&tag=%E4%B8%AD%E6%96%87
```

仅接受精确大写 `POST`／`GET`；POST 不允许配置 `query_parameters`。
GET 固定 URL 不得包含裸 `?`／`#`，包括末尾空分隔符；配置阶段即拒绝，避免查询进入 fragment 或改变参数名。
GET 按 argument 键排序，列表保留顺序并编码为重复参数。字符串、有限数字和布尔值
可单独使用或放入非空列表；布尔值编码为 `true`／`false`，字符串空值保留。
null、对象、嵌套／空列表、非法名称和未映射的实际 argument 在请求前拒绝。
映射中的可选 argument 缺省时不发送；空映射只接受无参数调用。名称须非空且无
空白／控制字符，目标参数名不能重复。名称和值均进行 UTF-8 百分号编码，参数不能改变
固定 host／path。GET 不发送请求正文或 Content-Type。

原 canonical JSON 输入与编码后查询的 UTF-8 字节数分别受 `max_input_bytes` 限制，
避免 Unicode 或参数名扩张绕过限制。GET identity 另外固定 `query_parameters`；
变更方法或映射须使用新版本并保留原运行配置。查询参数可能出现在服务访问日志中，
应用不要用查询参数传递秘密。

GET 不自动更改效果分类或审批要求；宿主仍必须注册明确的 `ToolPolicy`。
需要审批的 GET 继续等待原 Action 审批，保留稳定 effect key、关闭重开与重复回执语义。

## 生命周期与效果

每次调用拥有同步httpx.Client，沿原ambient和Source实际线程跟踪器执行并关闭。
取消调用方等待不会取消远端业务；Source停止准入、请求停止并等待真实处理器及
客户端关闭。关闭被取消可再次等待。`wait_for_calls()`只等待本Source真实调用。
timeout为(0,300]秒，限制各socket I/O并在操作间检查总deadline；它不是硬实时的
远端停止／墙钟上限。被阻塞的socket等待仍需实际退出，不能提前释放执行权。

下游请求可能已提交但响应丢失。idempotent_write通过原保留字段注入Action的
稳定effect key，下游负责幂等；unqueryable_write保留核验等待，不会盲目重发。
JSON工厂不接受Python reconciler；可查询写入由宿主使用SDK自定义注册。
任何工具成功回包均不替代业务Verifier，也不保证任意操作恰好执行一次。

## async 声明装配

`RuntimeBuilder.abuild`和`TemporalRuntimeBuilder.abuild`共用`tools/http-json`。
组件config只接受1–256个tools；每项必须有descriptor/url/version/policy，另可有
prefix/headers/timeout/max_input_bytes/max_output_bytes/method/query_parameters。未知字段、
非法方法／映射和重复名称在分配前拒绝，工厂通过原owned ledger关闭Source，
部分构造失败也排空已拥有资源。
同步装配在分配前拒绝并提示abuild。

```json
{
  "adapter": "http-json",
  "config": {"tools": [{
    "descriptor": {"name": "lookup", "description": "Lookup", "input_schema": {"type": "object"}},
    "url": "https://your-business.example/lookup",
    "version": "lookup-v1",
    "policy": {"version": "1", "effect": "read_only", "requires_approval": false}
  }]}
}
```

GET 可在同一个 JSON 工具声明中增加 `"method": "GET"` 和
`"query_parameters": {"query": "q"}`。等价 TOML 字段使用原组件结构：

```toml
[[profiles.components.tools.config.tools]]
url = "https://your-business.example/search"
version = "search-v1"
method = "GET"
# descriptor／policy 仍须按原结构显式声明。
[profiles.components.tools.config.tools.query_parameters]
query = "q"
```

配置预检只校验固定声明，不连接服务；GET 不新增客户端所有权或执行后端。

Temporal写工具仍需耐久EffectJournal；本适配器不增加执行数据库／Authority。
可以用另一ToolSource或显式组件工厂替换接口。CLI完整起步示例见[CLI指南](cli-tools.md)。
本轮[验收记录](../architecture/reviews/2026-10-11-fixed-business-tools.md)区分离线／
本机真实服务／安装恢复证据和未完成门槛。完整R12及框架对齐继续开放。
