# 框架更新与双语网站文档同步

日期：2026-11-09（Asia/Shanghai）。范围：审阅框架相对网站旧基线的增量，更新和验证本地网站文档。

## 源码基线

- 旧网站固定源码：`300c62ce8dd417df6b471ce1c10a1b7a562d2c46`。
- 新固定源码：`4bb46fe7a8935e6d13962a6c34e02519122c4c53`，SDK 基版本仍为 `0.1.0a8`，日期更新为 2026-11-09。
- GitHub API 已直接核对该公开提交；开发分支为 `codex/callable-preview-fixes`。核对时公开 main 为 `e94c57c9da5312bbcd69956620e543e9477ace99`，没有把开发增量说成已合入主分支或公开发行包。
- `repository.json` 增加显式 `publishedRef`；远端链接门禁核对所选公开分支的提交历史，普通文档链接仍使用完整 SHA。main 的当前交付别名保留原有精确路径规则。

## Review 结果与更新

| 同步缺口 | 处理 |
| --- | --- |
| 旧基线遗漏新增能力，并保留 Temporal 必须非空 Provider 的旧说明 | 固定新开发源码；分别说明 Local 普通 Tool／Transform 图与显式 Temporal executor 图的准入条件 |
| HTTP 只介绍 POST，缺少 GET 与参数映射 | 双语补 SDK 注册片段、参数编码、允许／拒绝输入、策略及生命周期；工厂装配仍使用 abuild |
| 展示策略只有 SDK 说明 | 补 JSON／TOML 对应关系、四个 bounded 字段及范围；明确配置不自动把 complete 改为流式调用 |
| 缺少通用异步节点的实际使用路径 | 增加完整离线审批／重开／一次效果／重放示例、完整 JSON identity Profile、Local／Temporal 支持矩阵、Journal 与容量限制 |
| API／测试没有新节点入口 | 增加 NodeExecutor 端口、registry/spec、workflow_executors、node-executor/core N01–N10、not_run／not_verified 与资源归属 |
| 本地资料助手缺少网站入口，容易混淆 SDK 与应用依赖 | 增加独立应用、精确私有 SDK 依赖前提、来源证据、报告预览／批准／恢复与文件核对，保留公开 SDK 连续教程 |
| Callable／Schema 修复对恢复的影响未说明 | 补稳定身份与外部依赖责任、Local 独立引用根、Temporal 引用子集及旧 Run 原版本恢复要求 |

保持 14 对指南与现有导航结构，更新中英文内容和 source-lock；本轮没有编辑 SDK 产品代码或历史验收；原未跟踪审查文件的内容摘要保持一致。

## 独立复核与实跑修正

一次全量只读复核提出三项 P2 和一项验证器缺口，均已处理：

1. 默认人工终端不显示来源 ID 或报告正文 SHA。改为通过 `--json status` 读取 `sources[].id` 和 `pending[0].sha256`，明确批准使用 `digest`，正文核对使用 `sha256`。
2. Temporal SDK 示例明确 `tools=ToolRegistry()`；注册表含任一非只读节点时必须有耐久 EffectJournal，即使当前图未使用它。
3. 节点 identity 必须为非空有限 JSON 对象；queryable_write 必须提供真正异步的 reconcile。
4. 验证器比对首次暂停的原 Action，默认检查明确核对 node-executor／core、N01–N10 和全部 not_verified；离线参考也核对准确 case 集合。故意从首条检查命令移除节点角色时，旧 guard 接受错误角色，补强后拒绝，反例已实际执行。

完整门禁首次实跑另发现证据路径的父目录不存在：原 `.ralf/node-evidence-1` 被 CLI 以 invalid_contract_configuration 拒绝。已将两种语言改为当前可写目录下的新 `node-evidence-1`，并说明父目录必须存在；没有修改 SDK 创建目录的契约。原失败日志保留在本轮临时验证目录。

## 验证

本轮本地验证与浏览器复验已完成。以下结果来自实际执行，所有门禁分项通过；没有将本地搜索结果写成线上网络故障已经修复。

| 检查 | 实际结果 |
| --- | --- |
| Astro 静态检查 | 最终 36 个文件，0 errors／warnings／hints |
| 网站测试 | 初轮 31/31；补充源码获取回归后，全套 33/33 通过 |
| 双语来源核对 | 14 对指南匹配已审阅的固定 Git 源文件与翻译摘要 |
| 双语离线教程门禁 | 模型工具／输出 Schema／原请求重放、Session、持久输入、混合检索、CLI 审批重启、连续应用、四组离线评估、事件游标与展示重放、无模型 Tool 审批均通过 |
| 新增开发源码教程 | 两种语言的 managed-node 审批／重开／原 Action 与一次效果、identity Profile、N01–N10 默认未运行及离线参考、HTTP GET 注册、TOML 展示策略均通过 |
| 构建与搜索索引 | 32 页、28 篇文档、2 种语言；2,027 个本地链接／资源目标通过 |
| 公开源码 | 56 个固定提交目标、1 个 main 当前交付例外通过；远端公开开发分支 tip 与固定 SHA 一致 |
| Cloudflare 预检 | Wrangler 4.151.3 dry run 退出码 0，仅预检构建资源，未发布 |
| 浏览器首次查询 | 本地构建中，中文“节点”返回 9 条中文结果；英文 `node-executor` 返回 4 条英文结果，均无需重试，结果含本次新增文档 |
| 浏览器交互 | 工作流及测试指南同页切换中英文正常；中英文新增节点命令均可复制，剪贴板含准确的新证据目录；搜索结果可打开测试指南 |
| 渲染内容 | 新节点教程、版本／固定 SHA／日期、资料助手的精确依赖与 JSON status 字段均在本地页面显示，截图保存在本轮临时验证目录 |

构建引导另补 `ensure-docs-source.sh`：单独获取声明的公开分支，确认固定提交对象存在，不 checkout、不 reset、不覆盖工作目录。真实临时 Git 夹具先证明仅克隆 main 时看不到开发提交；补取后固定源码可读、较新分支 tip 可用于祖先检查，HEAD 和本地草稿不变；可变源码引用在联网前拒绝。两项回归先 RED、后 GREEN，全套网站测试 33 项通过，Bash 语法及实际 JSON 元数据加载也通过。

完整 `npm run verify:production` 在本地检查、双语教程与构建通过后，因沙箱无法解析 github.com 停在远端核验。随后仅对失败的只读网络检查重跑，成功核对 `refs/heads/codex/callable-preview-fixes`；补跑余下的 dry run 也成功。原链路失败日志保留，没有改写为一次整链退出码 0。

- 固定源码从 Git 对象导出，在目录外普通安装到独立 SDK venv；借用宿主已安装的基础／构建依赖。461 个产品文件与固定源码逐字节一致，目录外 import 指向该 venv 的 site-packages。
- 本机默认 Node 22.9 无法运行 TypeScript 测试；实际门禁使用已安装的 Node 25.6.1，Python 3.12.7。首次临时 venv 未找到宿主用户目录中的 setuptools，显式复用基础依赖后安装成功；没有修改全局环境。
- Astro preview 子进程未就绪后，使用仅监听 `127.0.0.1` 的静态服务器复验同次 `dist`。Chrome 新建预览未成功，浏览器检查由应用内浏览器完成；测试结束已关闭临时页面与服务器。
- 真实模型、实际 HTTP 业务请求、Temporal Service、私有资料助手制品运行、公开发行和 Cloudflare 部署不属于本轮本地网站验证，未借用旧成绩计为本轮通过。

## 保留的框架边界

Temporal 节点的默认 16 槽 owner 不提供跨 Run 背压或自动容量排队；Schema 拒绝不撤销已保存的真实效果；展示、等待和终态均不替代实际处理器退出、ACK／Journal 和关闭责任。本轮将这些条件写进使用路径，没有修改 SDK 实现或扩大其支持资格。

公开 SDK 源码与资料助手的精确私有依赖属于不同安装组合。用户需要新的公开应用安装路径时，应另行调整并验收应用交付，网站文案不能代替包依赖变更。

## 改动隔离

任务开始时仅有原未跟踪审查文件；收尾期间检测到 SDK 与仓库技术文档新增并行未提交改动。本轮编辑范围为 `website/` 和本轮网站同步计划，未触碰这些并行 SDK／技术文档改动，也没有将其纳入固定源码或本轮验收。固定来源检查始终读取公开 `4bb46fe` 的 Git 对象。网站改动保留在本地，未推送、合入 main 或部署。

后续用户已明确授权独立发布；推送、Cloudflare 和线上验收结果见[本次发布记录](2026-11-09-framework-docs-deployment.md)。
