# 框架文档更新上线与复验

日期：2026-10-31（Asia/Shanghai）。站点：[relfagent.com](https://relfagent.com/)。

## 发布范围

用户在本地同步完成后明确授权推送并部署这次文档更新，再验收中英文文档、搜索、HTTPS 和 www 跳转；其他未提交改动保持不动。

- 网站实现提交：`4242ae4`；[本地同步与验证记录](2026-10-31-framework-docs-sync.md)。
- 教程固定公开维护源码：`300c62ce8dd417df6b471ce1c10a1b7a562d2c46`，SDK 基版本 `0.1.0a8`；维护源码、原归档和私有 wheel 的资格继续分开。
- 本轮仅发布网站文档及发布记录；没有 SDK 产品、制品或发布资格变化。
- 开始时的 `docs/current-delivery.md`、`docs/continuous-development.md` 和 `architecture/reviews/2026-10-30-framework-followup-review.md` 已保存字节摘要，排除于本轮提交，收尾时再次核对。

## 自动部署与验收

发布提交为 `e726846be36d458e2a3f020bcea126dc1d9e27d1`。原文档实现与发布记录已一起推送到 main，三个原有未提交文件未纳入提交，推送后内容摘要保持一致。

- GitHub [Website 工作流](https://github.com/RalfNick/relf-agent/actions/runs/41179912273) 已通过；终态日志确认静态检查 0 errors／warnings／hints、25/25 测试、14 对文档来源、双语完整教程、32 页构建、1,985 个本地链接／资源目标、50 个固定公开源码目标和 dry run 均成功。
- Cloudflare [构建 170e5810-578f-4c06-aaea-d0ddba50f1e0](https://dash.cloudflare.com/6fcab8530fe6ef0b32741fbf005326ce/workers/services/view/ralf-agent-website/production/builds/170e5810-578f-4c06-aaea-d0ddba50f1e0)。
- 构建：`bash scripts/cloudflare-build.sh`；部署与公网检查：`npx wrangler deploy && npm run cf:verify-live`。
- Cloudflare 构建与部署成功，完成于 **2026-10-31 15:23:48 Asia/Shanghai**；Worker 版本为 `b4e9e495-bfc9-4f73-ae5f-9b9a43e96d68`。

上述构建均由本次 Git push 自动触发。网站已经上线；浏览器搜索首次加载仍有验收保留项，详见下文。本记录不代表 SDK CI、SDK 制品或发布资格通过。

## 同次产物公网检查

Cloudflare 构建在发布后执行 `cf:verify-live`，检查时间为 `2026-10-31T07:23:47.276Z`（15:23:47 Asia/Shanghai）。[完整 95 项结果](2026-10-31-framework-docs-http-checks.json) 来自本次构建的终态日志，全部首次请求通过，失败数为 0。

| 范围 | 结果与边界 |
| --- | --- |
| 84 个公开文件 | 中英文页面、静态资源、Pagefind JS／WASM／索引／片段、robots 和 sitemap 的响应字节与同次构建产物 SHA-256 一致；涵盖 14 对文档，防止旧 HTML 与新搜索索引混用 |
| 9 种跳转组合 | HTTP 主域名、HTTP www、HTTPS www，分别检查首页、英文 API 和中文快速开始；均为 301，目标为 HTTPS 主域名，路径与查询参数保留 |
| 自定义 404 | 返回 404，页面内容摘要与同次产物一致 |
| 末尾斜杠 | `/en/docs/quickstart` 返回 307，补齐斜杠 |
| HTTPS | Node fetch 使用默认的证书链与主机名校验；没有绕过 TLS 校验。公网检查通过不等于所有访问网络的延迟均通过 |

## 浏览器复验

在 Google Chrome 中直接访问线上站点，结果如下。浏览器操作与公网字节校验相互补充；搜索资源存在不能代替真实查询验收。

| 项目 | 观察结果 |
| --- | --- |
| 中英文文档内容 | 安装页、快速开始、API、连续应用教程及中文能力总览显示 SDK `0.1.0a8`、固定维护源码 `300c62ce8dd4` 与验证日期 `2026-10-31`；新 API、`agent_app.journey`／`customize` 和框架优化说明已上线 |
| 语言切换 | API 与连续应用教程的中英文切换保持同一文档路径，内容对应 |
| 教程代码复制 | 中英文连续应用教程的首段代码均可复制，剪贴板实际内容与页面命令一致，包含 `python -m agent_app.journey --help` |
| 中文搜索 | 首次输入 `subscribe_events` 后进入超时提示；点击一次“重试搜索”后返回 5 个中文结果。结果中的“API 与 CLI 参考”可正常打开，包含本次新增的可恢复事件与展示流说明 |
| 英文搜索 | 首次输入 `stream_updates` 后进入超时提示；点击一次“Retry search”仍未恢复。随后“Browse documentation”降级入口可正常打开英文快速开始 |
| www 跳转 | 浏览器访问 `https://www.relfagent.com/zh/docs/quickstart/?q=approval%20resume&x=1`，最终到达 `https://relfagent.com/zh/docs/quickstart/?q=approval%20resume&x=1`，文档正常显示；完整协议组合另由上表 9 项检查覆盖 |

## 搜索验收保留项与排查证据

**本轮不能将搜索首次加载记为通过。** 中文重试后可用，英文首次及一次重试均超时。两种语言均受影响，尚不能把问题归因于中文分词或本次文档内容。

在浏览器验收期间，对同次构建中的 5 个公开 URL 另做本机 curl 连接／传输探测，每次上限 20 秒，没有关闭证书校验。5 项都未完成：

| 路径 | 结果 |
| --- | --- |
| `/pagefind/pagefind.js` | 连接超时，HTTP 状态未收到，20.010 秒 |
| `/pagefind/index/zh-cn_98cd513.pf_index` | 已收到 HTTP 200 响应头，但 34,113 字节响应体收到 0 字节后超时，20.010 秒 |
| `/pagefind/fragment/zh-cn_1f45b5d.pf_fragment` | 连接超时，HTTP 状态未收到，20.011 秒 |
| `/pagefind/fragment/en_1e30a52.pf_fragment` | 连接超时，HTTP 状态未收到，20.005 秒 |
| `/zh/docs/installation/` | 连接超时，HTTP 状态未收到，20.001 秒 |

这些结果表明本机到站点的连接与传输也存在异常；Cloudflare 构建环境对同次产物的 95 项检查均首次通过。现有证据不足以唯一确定浏览器搜索超时的根因，本轮保留现有搜索实现，并将首次加载列为待复核项。

后续需在稳定访问网络中，以未加载相应语言索引的浏览器上下文重新验收上述两条查询，并记录索引、词块与结果片段的请求时序；区分连接／响应体停滞和查询逻辑耗时后再决定修复。本次上线验收结论为：**自动部署、文档、HTTPS 与跳转通过，搜索首次加载有保留项。**

## 收尾与改动隔离

本轮验收材料单独提交。开始时的三个未提交文件经 SHA-256 再次核对，内容逐字节保持一致，未纳入本轮任何提交；没有执行 stash、restore 或 reset。
