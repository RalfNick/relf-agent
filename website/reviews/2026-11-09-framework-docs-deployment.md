# 网站文档独立发布与上线验收

日期：2026-11-09（Asia/Shanghai）。站点：[relfagent.com](https://relfagent.com/)。

## 授权与发布范围

用户明确授权将本次网站文档更新单独提交、推送 main 并部署 Cloudflare，上线后验收中英文文档、搜索、HTTPS 与 www 跳转；SDK 未提交改动保持不动。

- 发布以公开 main `e94c57c9da5312bbcd69956620e543e9477ace99` 为父版本，使用独立工作目录。
- 只包含网站文件、本轮网站同步计划与验收记录；不合入开发分支的 SDK 提交，不复制原工作区的 SDK／技术文档未提交改动。
- 教程固定到已公开开发源码 `4bb46fe7a8935e6d13962a6c34e02519122c4c53`，基版本 `0.1.0a8`；保留其公开开发分支和私有验证包的范围区分。
- 同时携带网站所需的固定 Git 来源读取和 current-delivery 精确链接转换，避免仅复制翻译而缺少 main 尚未包含的配套网站代码。
- [文档 review 与本地验证](2026-11-09-framework-docs-sync.md)保留原历史结果；本记录追加本次发布证据。

## 发布前验证

在隔离 main 副本执行完整正式网站门禁，确认源码固定、双语教程、构建与 Cloudflare 预检；原工作区 SDK 文件清单和 SHA-256 已保存，收尾时再次核对。

隔离 main 的完整 `npm run verify:production` 已以退出码 0 通过：36 个文件静态检查零错误／警告／提示，33/33 测试，14 对固定 Git 来源，中英文完整离线教程，32 页／28 篇文档搜索索引，2,027 个本地目标、56 个固定公开源码目标与 Cloudflare dry run。

验证使用 Python 3.12.7、Node 25.6.1 和隔离安装的 main SDK；教程运行时按既有门禁导出并使用固定 4bb46fe 源码。首次临时环境误用宿主 Python 3.10，在 tarfile filter 参数处失败；明确切换 Python 3.12 后整链重跑通过，保留初次环境失败日志。

原工作区没有切换分支、暂存、提交、stash、restore 或 reset。本轮操作只写隔离发布目录与临时验证材料。核对时 SDK 产品／测试文件摘要保持；观察到并行任务继续更新仓库技术文档、设计／评审记录及评估产物，保留其最新内容，不回写或还原。收尾与起始清单比较，SDK 产品／测试文件摘要仍一致，11 个非网站文档或评估路径发生并行变化；原分支和 HEAD 仍为 `codex/callable-preview-fixes`／`4bb46fe7a893`，未被本轮发布操作移动。

## 自动部署与上线验收

本次发布已完成，浏览器搜索验收仍有未通过项，不能记为整站全绿。

- 文档发布提交：`b7bb4e71d3d1ef50fcfe225c4654864125b79871`；格式修正后的实际部署提交：[`4fb811af9ff8c2b45b2afea851abb3753f697faa`](https://github.com/RalfNick/relf-agent/commit/4fb811af9ff8c2b45b2afea851abb3753f697faa)。两次均普通快进推送至 main。
- [GitHub Website 工作流 42585586583](https://github.com/RalfNick/relf-agent/actions/runs/42585586583)：success，33/33 测试、双语教程、32 页／28 篇索引、2,027 个本地目标与 56 个固定公开源码目标通过。
- [Cloudflare 构建 5d918017-a477-4638-b4e5-28d97f5a3ce2](https://dash.cloudflare.com/6fcab8530fe6ef0b32741fbf005326ce/workers/services/view/ralf-agent-website/production/builds/5d918017-a477-4638-b4e5-28d97f5a3ce2)：success；Node 24.22.2／Python 3.12.7；Worker `ralf-agent-website`。
- 实际 Worker 版本：`be82d9dc-f8f6-49a4-9a32-f1f3089667aa`，部署完成于 2026-11-09 16:28（Asia/Shanghai）。
- 同一构建执行 `npx wrangler deploy && npm run cf:verify-live`。公网门禁开始于 `2026-11-09T08:28:12.465Z`，报告 `86 assets, 9 redirects, custom 404 and trailing slash; 0 failures`：共 97 项。资源正文按该次构建 dist 的 SHA-256 验证，HTTPS 使用默认 TLS／主机名验证，没有跳过证书检查。完整逐 URL 输出保留在上述 Cloudflare 构建日志；[结构化摘要](2026-11-09-framework-docs-http-checks.json)不冒充完整逐请求日志。

| 验收项 | 实际结果 |
| --- | --- |
| 中英文文档与静态资源 | 公网门禁通过全部 86 个资源；包含两种语言的全部 14 篇指南及 Pagefind 资源。浏览器抽查新增 Workflow、Testing、API 和连续应用教程，显示固定源码 `4bb46fe7a893`／验证日期 2026-11-09。 |
| 文档准确性与语言互切 | 浏览器确认受管理异步节点、N01–N10、NodeExecutor API、独立资料助手的私有精确依赖说明；Workflow 与 Testing 互切保持同一指南，中英文应用依赖边界一致。 |
| HTTPS | 同次公网门禁通过；Chrome 正常打开正式页面，没有证书拦截页。 |
| www／HTTP 规范化 | 9 个 301 全部通过，保留路径及查询参数；Chrome 访问 `https://www.relfagent.com/zh/docs/quickstart/?q=approval%20resume&x=1`，实际落到相同路径和参数的 HTTPS 主域名。无尾斜杠地址返回 307，未知页面为预期自定义 404。 |
| 中文首次搜索 | **未通过**。生产 Chrome 新页查询“节点”出现“搜索暂时不可用”；重试仍失败。另一快速开始页已完成索引预热，但查询阶段仍触发失败提示。没有把预热／重试结果充当首次成功。 |
| 英文首次搜索 | **未通过**。生产 Chrome 新页查询 `node-executor` 出现暂不可用提示。 |
| 搜索降级 | 中英文失败后均显示重试与文档目录入口；目录导航可正常继续使用。 |

### 搜索失败的调查与待办

本次生产搜索不能依据构建成功或静态文件 200 判定通过。当前机器直接读取 `pagefind.js` 耗时约 11.0 秒，索引入口约 7.6 秒；只读 Node 探测使用页面相同的 `zh-CN`，能加载中文元数据、WASM 与查询索引，但某个结果片段连接 Cloudflare 地址时触发 `UND_ERR_CONNECT_TIMEOUT`（10 秒连接上限），其余已完成片段也有约 5–8 秒请求。Chrome 另记录 Pagefind Worker 初始化超时并回退主线程。

这些证据确认当前验收网络存在搜索子资源连接失败；尚不足以排除浏览器 Worker／加载流程还需优化。没有更改超时值来掩盖失败，也没有修改用户网络、全局缓存或安全设置。待办：在另一可用网络复测真正冷启动并采集完整请求时序，区分 Worker 启动、索引和片段请求；如仍能复现，再针对实际失败边界修复，并增加浏览器生产搜索门禁。现有自动公网门禁覆盖文件完整性，不等于执行过浏览器搜索交互。

### SDK CI 的范围与状态

格式修正后的 [SDK CI 42585586818](https://github.com/RalfNick/relf-agent/actions/runs/42585586818)在收尾查询时仍为 in_progress，三个 Python 测试矩阵与 remote-contracts 尚无最终结论。Website 工作流与 Cloudflare 发布已独立 success。本轮不修改 SDK 实现，不把仍在执行的 SDK CI 记为通过；此前 SDK 待办继续保留。

验收记录使用独立的 `[skip ci]` 提交回存 main，只更新仓库说明和证据，不改变上述已上线网页产物。

## 首次推送的 CI 格式修正

首个独立网站提交为 `b7bb4e71d3d1ef50fcfe225c4654864125b79871`，父版本为 e94c57c，37 个变更路径均属于网站及其计划。推送 main 后触发 Website 工作流与 Cloudflare 构建。

同次 SDK CI `42584877291` 在 Ruff 格式检查失败，定位为本次 `website/scripts/check-tutorials.py`，并非 SDK 实现失败。随后使用 CI 相同的 Ruff 0.17.4 仅格式化该网站脚本；格式前后 Python AST 完全一致，隔离 main 的 `ruff check .` 与 `ruff format --check .` 均通过（1,508 个 Python 文件）。保留首次失败，修正以新的普通提交重新触发检查和部署，不改写已推送历史。
