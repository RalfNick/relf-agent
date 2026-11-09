# 中英文首次搜索超时修复与发布验收

日期：2026-11-09（Asia/Shanghai）。用户授权修复首次搜索与重试，推送 main、部署 Cloudflare；其他 SDK 未提交改动保持不动。使用现有隔离网站工作区，基线为 main `4a23b7a0e09d7e60cf03ef572340b5eb47259031`，只提交 `website/**`。

## 原因与修复

[上一轮生产失败](2026-11-09-framework-docs-deployment.md)确认：当前网络读取搜索资源耗时数秒，片段出现连接超时；浏览器同时记录 Worker 初始化超时并回退。原路径串行加载运行时、Worker、入口、语言索引、WASM、查询分块和结果片段；查询用 Promise.all 等待全部片段，任一失败就丢弃整次结果。重试重建同一网络链，30 秒初始化／12 秒查询预算仍无法保证成功。

当前每种语言仅 14 篇指南。构建继续通过 Pagefind 提取实际渲染正文与代码，去除分词用的零宽字符，把当前语言的完整快照内嵌到 HTML。浏览器本地执行大小写／Unicode 归一化后的全文包含匹配，多关键词 AND、标题优先，保留 API 下划线／连字符、原中文标点与代码文本。正文中原有 `<tool>`、`</script>` 等按数据转义并使用 textContent 展示。

正式页面的快照初始化不执行 Pagefind 导入、Worker 或片段请求；原总预算未提高。失败后清理原实例，重试重新读取页面快照并保留关键词。快照检查版本、语言、URL 范围、重复项、完整指南覆盖和 300 KB 未压缩上限。构建门禁检查所有搜索页面的同语言快照一致，并实际执行两种语言的 API／审批查询。

代价：每页增加一份当前语言数据；最终原始快照中文 134,831 B／gzip 52,562 B，英文 151,915 B／gzip 49,138 B（内嵌 JSON 转义和 HTTP 压缩会使实际大小略有差异）。该小语料检索不提供词干化或语义搜索，增长超出预算时构建会失败并要求重新评估传输方式。没有在正式站加入故障注入开关。

## 本地验证

- 按 test-driven-development 先加入“搜索网络永不连接时仍可从页面快照查询”的回归：旧实现触发 Search request timed out，修复后通过；另以中文标点被错误归一化的失败用例验证修正。
- 完整 `npm run verify:production` 退出码 0：Astro 38 文件零错误／警告／提示，40/40 网站测试，14 对来源、两种语言完整离线教程、32 页、2,027 个本地目标、56 个固定公开来源与 Cloudflare dry run。后续中文标点修正只影响搜索正文，重跑整个网站测试与构建均通过。
- 浏览器使用实际生产构建，临时预览服务器令所有 `/pagefind/*` 请求返回 503。中文首次“节点”得到 9 条，英文首次 `node-executor` 得到 3 条，填词到结果可见分别 248 ms／239 ms（工具壁钟，含自动化开销）。结果均为当前语言文档。
- 中英文受控故障页先给损坏的快照，打开搜索后确实出现失败提示；通过仅存在于临时测试页的按钮恢复同一构建数据，再点击产品原有“重试搜索／Retry search”，得到 9／3 条，原关键词保留。测试修改的是临时服务器返回的 HTML，未修改产品数据或加入生产测试后门。
- 上述首次查询和故障重试结束时，预览服务器共收到 20 个请求，`pagefind_requests=0`；搜索不依赖被阻断的运行时／WASM／分块／片段。
- 原 SDK 工作区只读保存分支、HEAD 与 35 个未提交文件的摘要，收尾再核对；不切换、不暂存、不提交、不恢复其内容。

## main 与生产复验

- 已普通快进推送 main：[`f08104d39814ce1ab74716fc902b3ef4dad6a158`](https://github.com/RalfNick/relf-agent/commit/f08104d39814ce1ab74716fc902b3ef4dad6a158)，9 个路径全部属于 `website/**`。
- [GitHub Website 42593376121](https://github.com/RalfNick/relf-agent/actions/runs/42593376121) success：Node 24 环境的 40/40 测试、双语教程、全文快照与完整产物门禁通过。
- [Cloudflare 构建 9e7fc8f2-d720-483b-81fc-a06ec31422a7](https://dash.cloudflare.com/6fcab8530fe6ef0b32741fbf005326ce/workers/services/view/ralf-agent-website/production/builds/9e7fc8f2-d720-483b-81fc-a06ec31422a7) success，外部检查完成于 `2026-11-09T09:31:02Z`（17:31:02）。Worker `ralf-agent-website` 的实际版本为 `bdf2883a-7886-4c6f-bd34-5a496f379225`。
- 同次部署门禁确认 86 个资源的正文 SHA-256、9 个 HTTP／www 保留路径和查询参数的跳转、自定义 404 与尾斜杠，共 97 项、0 失败。HTTPS 使用默认证书与主机名验证。逐 URL 日志保留在该 Cloudflare 构建。

| 正式 Chrome 验收 | 结果 |
| --- | --- |
| 新中文快速开始页的首次查询“节点” | 9 条，261 ms |
| 新英文快速开始页的首次查询 `node-executor` | 3 条，235 ms |
| 中文 `subscribe_events` | 5 条；清空后查询、重复 Enter、关闭重开后重新输入均正常 |
| 英文 `stream_updates` | 5 条 |
| 英文运行文档切换到中文后查询 `stream_updates` | 5 条中文文档 |
| 中文搜索结果导航 | 正常打开 `https://relfagent.com/zh/docs/api-reference/` |
| 英文搜索结果导航 | 正常打开 `https://relfagent.com/en/docs/operations/` |
| 浏览器日志 | 本轮正式中英文页面没有捕获到 error／warn，未再出现 Pagefind Worker 初始化超时 |

以上查询耗时是填词到结果可见的工具壁钟，包含自动化开销，不包括网页导航及初始 JavaScript 下载；首次指新页面首次查询，没有修改用户网络或清空全局缓存。页面完成导航后再交互；旧页面需要刷新后加载新版本。

故障重试的受控注入在本地完成：先失败、恢复同一构建快照、点击原重试按钮、保留关键词并成功。正式站没有注入损坏数据。生产页面实际引用的 `/_astro/Search.astro_astro_type_script_index_0_lang.qOTbaixb.js` 与本地故障验收的构建文件一致，正式重复查询及结果导航正常；不能把这些结果表述为在正式站执行过故障注入。

[结构化验收结果](2026-11-09-search-acceptance.json)记录查询、耗时、重试范围、CI、Cloudflare 和工作区保护核对。本轮其他 SDK 未提交改动保持原样：收尾重新核对 35 个文件摘要全部一致，原分支和 HEAD 均未移动。SDK 工作流的全量结论不包含在网站 CI success 中。

最终证据以独立 `[skip ci]` 提交回存 main；只更新 review／JSON，不改变已上线的网页和 Worker 版本。
