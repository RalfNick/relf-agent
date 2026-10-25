# 自定义 CLI Engine 校验与失败清理修复

日期：2026-10-25。维护基线 `6ab0d9ce08de802225020d3149cf0ee93540a6ca`。继续优化已交付框架的扩展失败边界，不增加 Agent、编排、适配器、协议或执行权威。仅本地提交、单次跳过钩子；不推送、触发远端 CI、调用真实模型或公开发布。

## 问题与修复

复现：可信 CLI 工厂创建持有真实 SQLite Coordinator 的 Engine，返回的代理在读取 `drive` 属性时抛普通异常。原 `validate_engine` 原样抛出该异常，`load_engine` 仅捕获 ValidationError，所以没有关闭已返回对象；第二个 Coordinator 仍被阻断。

- 公共 Engine 校验将普通属性／方法形状读取异常转换为 `ValidationError`，与既有组件校验一致；`RalfError` 保留原类型，控制中断不转换为配置错误。校验不调用业务方法或取得新执行权威。
- CLI 对工厂返回后的全部校验失败承担已有同步清理责任；成功关闭后原样传播原错误或中断。清理的属性读取或调用失败，包括 KeyboardInterrupt／CancelledError／SystemExit，复用 `RuntimeBuildError.cleanup` 保存原对象供明确重试。
- 独立复核发现 `getattr(..., None)` 会将已声明 close 属性抛的 AttributeError 吞作“缺少 close”。反例先失败；现在区分静态声明存在但读取失败与真正缺失，前者保留原异常和清理句柄。没有进入不支持的异步 close，也没有自动调用工具或创建 Run。

工厂抛错前尚未返回的资源、借用客户端以及不满足同步关闭协议的对象，仍由工厂或宿主管理。保留的 cleanup 对象只用于显式关闭／修复后重试，不自动授予业务恢复。原生生成器／coroutine 的既有清理分支及任意可信 Python 的伪装／内部行为不在本次扩展范围。

## 测试与验收

`tests/test_cli_factory_cleanup.py` 使用真实 LocalEngine、SQLite连接和租约，覆盖普通错误、三类控制中断、已有框架错误、清理中断、close属性读取失败及CLI结构化错误。成功清理后旧连接实际关闭、新Coordinator可取得且无Run被创建；失败清理时第二个Coordinator被拒绝，拿原句柄重试后再验证释放。不以 mock 调用次数代替资源证明。

- 初始12项：**11 failed／1 passed**，原日志和JUnit保留。
- 首轮修复：12 passed。
- AttributeError反例：**1 failed／1 passed**；本次失败是重试句柄丢失，未改变门槛。
- 最终13项：**13 passed**，warnings-as-errors。
- 相邻首轮32模块：450 passed，warnings-as-errors；早于AttributeError补丁，只保留为中间结果，不代替最终复验。
- 最终相邻回归：**32模块451 passed／零失败、错误、跳过**，`-W error`，132.42秒；CLI／配置／同步及异步装配／Runtime代理／服务生命周期／Agent Session和端口均按本次选择运行。它不是全量SDK回归，和13项有重叠，不累加。
- Ruff建议将固定名称getattr改为等价直接属性读取后，再跑最终13项全部通过；保留首轮样式报错，最终Ruff、1437文件格式与Git空白检查通过。
- 独立只读复核先运行原12项通过，发现上述AttributeError边界；同一次复核查看修复、回归与文档后，未发现本批差异剩余可行动P1／P2／P3。不将其视为整个框架审计。
- 独立CLI子进程对比：同一错误适配器，原a7安装环境退出1且无显式关闭标记；维护源码退出2、输出validation_error且不暴露底层异常正文，实际关闭标记存在。两者均零Run接受。原包缺陷不因源码测试通过而被报绿。
- 原a7来源预检使用原两包和原manifest，对当前维护源码按预期返回 `source_product_tree_mismatch`，未转交candidate；属于保护边界验证，不修改原门禁。
- 网站25项、14对双语文档来源摘要、49个固定目标及681个修改文档本地链接通过；网站继续固定a6的ba1c81f，不改教程、SDK基线或部署。

证据位于 `dist/extension-review-20261025/`。本轮只按影响范围运行离线源码回归，不运行全量SDK、S2、函数指纹专项、真实模型或实际远程服务，也未构建或安装新发行包。

## 原制品与发布边界

开始前保存了874个既有文件的摘要，覆盖完整a6／a7交付、原架构review及历史门禁清单；结束时逐一复核。产品修改仅 `cli.py` 和 `ports.py`，没有改变版本字段、依赖、Schema、Run／Action／组件身份或执行状态机。

当前维护源码与原a7产品树不同。a7 wheel／sdist、固定门禁及已有平台报告保持；不能把本批源码成绩标成原包通过。新补丁暂记 Unreleased，不重建同版本包。若发行补丁，另行准备唯一版本候选并独立验收；继续原a7发行则使用产品匹配的固定源码。

## 最终核对

874个保护文件摘要全部一致，a6／a7原包、原交付回执、冻结门禁及历史review未变。本次源码产品差异仅 `ports.py`／`cli.py`；版本和构建元数据保持，不生成新的同版本wheel。README、变更记录、扩展／装配指南和当前发布状态明确区分维护源码与原候选。证据摘要见本批 `acceptance.json`、`review.json` 和 `SHA256SUMS`；完成后仅本地提交，保留 `[skip ci]`，单次跳过钩子且不改永久配置。
