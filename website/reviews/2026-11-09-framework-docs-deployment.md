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

原工作区没有切换分支、暂存、提交、stash、restore 或 reset。本轮操作只写隔离发布目录与临时验证材料。核对时 SDK 产品／测试文件摘要保持；观察到并行任务继续更新六份仓库技术文档，保留其最新内容，不回写或还原。

## 自动部署与上线验收

待记录本次 main 提交、GitHub Website 工作流、Cloudflare 构建与 Worker 版本、同次产物公网检查，以及浏览器首次搜索、语言切换、HTTPS 和 www 跳转结果。

## 首次推送的 CI 格式修正

首个独立网站提交为 `b7bb4e71d3d1ef50fcfe225c4654864125b79871`，父版本为 e94c57c，37 个变更路径均属于网站及其计划。推送 main 后触发 Website 工作流与 Cloudflare 构建。

同次 SDK CI `42584877291` 在 Ruff 格式检查失败，定位为本次 `website/scripts/check-tutorials.py`，并非 SDK 实现失败。随后使用 CI 相同的 Ruff 0.17.4 仅格式化该网站脚本；格式前后 Python AST 完全一致，隔离 main 的 `ruff check .` 与 `ruff format --check .` 均通过（1,508 个 Python 文件）。保留首次失败，修正以新的普通提交重新触发检查和部署，不改写已推送历史。
