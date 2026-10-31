# 框架文档更新上线与复验

日期：2026-10-31（Asia/Shanghai）。站点：[relfagent.com](https://relfagent.com/)。

## 发布范围

用户在本地同步完成后明确授权推送并部署这次文档更新，再验收中英文文档、搜索、HTTPS 和 www 跳转；其他未提交改动保持不动。

- 网站实现提交：`4242ae4`；[本地同步与验证记录](2026-10-31-framework-docs-sync.md)。
- 教程固定公开维护源码：`300c62ce8dd417df6b471ce1c10a1b7a562d2c46`，SDK 基版本 `0.1.0a8`；维护源码、原归档和私有 wheel 的资格继续分开。
- 本轮仅发布网站文档及发布记录；没有 SDK 产品、制品或发布资格变化。
- 开始时的 `docs/current-delivery.md`、`docs/continuous-development.md` 和 `architecture/reviews/2026-10-30-framework-followup-review.md` 已保存字节摘要，排除于本轮提交，收尾时再次核对。

## 自动部署与验收

本轮通过现有 main／Cloudflare Workers Builds 流程执行检查、构建、发布与同次产物公网验收。此提交用于触发自动部署；实际构建编号、结果及浏览器复验将在完成后补录。
