# 框架优化后的双语文档同步验收

日期：2026-10-31（Asia/Shanghai）。文档源码固定 `300c62ce8dd417df6b471ce1c10a1b7a562d2c46`；SDK 基版本 `0.1.0a8`。GitHub 只读查询与最终远端链接检查均确认该提交已在公开 main 上。

## 同步范围

同步 14 组中英文指南、共享版本说明、首页安装说明与维护 README；技术源和译文快照同步记录。

| 内容 | 更新后的使用路径 |
| --- | --- |
| 安装与版本 | 固定公开维护提交，检查 Git ref、CLI 与 pip check；明确原 a8 归档、维护源码和私有冻结 wheel 的区别 |
| Agent 入口 | 完整离线 Agent＋async Tool 例子，submit／WaitResult、重放、显式 Registry 与效果声明 |
| 连续应用 | 安装后生成 journey／customize；五阶段应用、实际模型／异步工具／记忆替换入口及资源归属 |
| 事件与重连 | 交付游标续读、关闭重开后 attach 原 RunRef、暂停／观察取消边界 |
| 展示流 | 显式策略、模型流包装器、工具 JSON 进度、权威事实／gap、限额与失败关闭责任；原日志重放而非重调业务 |
| Local Tool 图 | 显式空 Provider、两个 async Tool、提交／恢复／重复回读、逐节点审批及原回执去重 |
| API 与故障 | 等待／关闭预检、owned／borrowed 生命周期、CLI 业务后关闭失败、扩展有限 JSON 返回值和原请求恢复 |

新增完整 Python 示例与命令配方在中英文中逐段一致；原 API 示意仅保留一处翻译后的注释差别。旧 a6 版本文字、连续教程手动下载应用文件路径，以及与新展示流矛盾的“所有片段都不是持久事件”表述均已修正。

## 实际验证

- 隔离 Python 3.12 环境安装准确源码快照，CLI 为 `Relf-Agent 0.1.0a8`，pip check 无依赖冲突；安装没有使用私有 wheel。
- 完整 `PUBLIC_SITE_URL=https://relfagent.com PYTHON_BIN=<隔离环境> npm run verify:production` 退出 0。
- 静态检查 0 errors／warnings／hints，网站单元测试 25/25，14 对双语快照通过；43 个技术来源的实际字节与固定 Git 提交完全一致。
- 两种语言的旧教程与新增路径全部通过：模型／Schema 新请求身份、Session 延续与重放、持久输入、Hybrid、审批跨进程恢复、五阶段生成应用及组件定制、四类离线评估、Agent 回读、事件游标／重开、流重放、纯工具图及两次逐节点审批。
- 展示流首次实际 model/tool 调用为 2/1，原 Run 重放为 0/0，事件及游标不变；纯工具图最终 0 Model Action／2 Tool Action／2 credits，重复批准与提交保持原 Run／回执。
- 首次待批正确为 1 个已提出的 Tool Action、0 credits。验证器初版将 Action 数误当作 handler 次数并失败；已依据实际原事实修正断言，并在中英文明确两种计数的差别。未修改 SDK。
- 四类评估均核验实际 completed、全部案例通过、调用数及 model_quality=null，未把 not_run 或退出码 0 单独视为通过。
- Astro 构建 32 页，Pagefind 索引 28 篇文档、2 种语言；1,985 个本地链接／资源目标、50 个公开固定源码目标与 Wrangler dry run 通过。
- 本地 Chrome 构建产物验收：中文首次查询 subscribe_events 返回 5 条中文结果；从结果打开 API 页并切换英文仍保留当前主题，英文 stream_updates 返回 5 条英文结果，均无需重试；连续教程首个生成命令的复制文本与页面代码一致。新增目录锚点及页面渲染正常。

独立只读复核未发现可操作问题；复核者独立核对全部 14 对译文及 43 个固定来源摘要。未重复执行完整 SDK／平台、在线模型或 Temporal Service 验收，也不据这些网站检查授予新资格。

## 执行判断与边界

- 沿用当前工作区，只提交本次文档路径；开始时已有的 current-delivery、continuous-development 和 framework-followup-review 三个文件逐字节保留并排除暂存，避免混入另一批目标调整。
- 按当前交付冻结策略仅本地提交，不推送、触发远端 CI、部署或公开发行；生产站本批未更新。解除冻结后仍可使用原网站自动检查／构建／发布流程。
- “不依赖仓库 examples”指默认 journey／customize 的安装后起步。独立展示流例子仍明确回到固定公开源码 checkout，再复制同一提交的 standalone 文件，不导入 examples 包。仅有安装包且无 checkout 的读者需先取得该公开源码；这条路径没有被写成生成模板能力。
- 保留实际 SDK 标识、旧配置和历史制品。源码基版本相同不代表维护能力或私有候选资格相同，旧 Run／History 不自动迁移。

本批剩余必要工作为无；独立采用、更多平台和公开发行继续按原当前交付范围单列。未触碰或关闭其待办。
