# 有界动态批处理验收

2026-11-10，基线 `aa77b90`。本批按有限范围验收完成：提供显式 `FanOutDAGPlanner`、原工厂装配及无需模型的完整应用。开发源码、本批私有候选、原推荐组合、公开main／官网与历史Alpha分别固定；不推送、触发远端CI或公开发布。

## 架构与使用边界

Planner只提出原DAG，使用原ValueRef列表索引绑定和InputMap结果映射；不保存第二套执行状态，不派发、结算或重试。稳定map-0000等ID对应输入索引，结果是JSON对象，不是完成顺序数组。可选reduce是原已注册汇总成员，须等全部Worker结果已采纳；不提供并发共享reducer、循环、逐记录流式Workflow或自主重规划。

无汇总最多256项，有汇总最多255项，路径最多31段；空列表、错误路径、缺成员、超限及非初始revision／结果拒绝。SDK／Local build与abuild、JSON／TOML及Temporal abuild使用显式工厂；默认Planner整表不加入新策略。应用可替换原受管理Graph／Agent成员，仍服从所选执行后端的既有组合范围。

## 实际验证

| 分层 | 本批实际结果 |
| --- | --- |
| 缺实现RED与纯策略 | 修正pytest保留参数名的收集夹具后，61项有效缺实现RED；实现后61/61通过 |
| 工厂与配置 | 有效RED为23失败／1通过；最终24/24通过，涵盖非默认alias／path实际执行及同步／异步装配 |
| Local新执行 | 13/13通过：反序完成、有界并发、可选汇总、严格授权、审批重开、零预算、取消、unknown和独立业务回执；3类真实SQLite进程切点均沿原10秒期限恢复 |
| 最终定向集合 | 源码与checkout外准确安装同22模块、498个ID全部通过／零跳过，JUnit 97.007／100.624秒 |
| 真实Temporal | 同2个ID源码与准确安装各2/2通过，JUnit33.574／39.130秒；正常批处理及审批静止窗口Worker进程重启、重复命令、History重放 |
| 纯运行依赖 | 15条检查通过，无pytest／Temporal SDK；指南首Python块原文及完整离线示例在checkout外通过；完成4次业务调用，原命令重放零新增调用 |
| 构建与安装 | wheel／sdist466产品与构建副本一致；sdist重建466产品逐字节一致，重装后原示例继续重放成功 |
| 所选兼容 | 旧guards／新源码／准确安装的普通Local与Temporal Release、默认策略表、节点与检索身份、8个catalog摘要相同 |
| 同冻结输入完整离线 | 15816通过／915条件跳过、零失败／错误，共16731项，JUnit2513.344秒，runner2516.292秒；自然退出0 |

完整轮保留原16631个测试ID及原通过状态；新增100项，最终498个定向ID在整轮均通过。两个新增Service用例在离线轮按条件跳过，其实际服务资格来自上表独立运行。原五个编排10秒崩溃窗口和本批三个SQLite切点均通过，原7200秒整轮看门狗保持。冻结466产品／1588执行输入未变，原pytest／guard进程组退出，防睡眠交接成功。

真实Service每例独立账本均为规划1次、Worker3次、汇总1次，4个不同效果键／4张回执；每例保存并实际重放10份History后业务账本不变。8个原始pytest／Worker PID均已退出，Worker关闭标记和Service shutdown成功；审批前的首Worker被测试kill并wait，替代Worker正常退出0。测试进程模块来源由已通过的ready.package == r.__file__断言和同进程replay import推导，没有补造独立replay路径证据。数学审计工具不证明任意外部写恰好一次；冷重启仅审批静止窗口，不代表在途物理handler全冷恢复。

## 准确候选与历史保留

| 本批私有制品 | 准确值 |
| --- | --- |
| SDK | `0.1.0a8+fanout.b4d9e82927e77bf2`；466产品，1588执行输入 |
| wheel | `dist/fan-out-20261110/sdk-artifacts/relf_agent-0.1.0a8+fanout.b4d9e82927e77bf2-py3-none-any.whl` |
| wheel SHA256 | `786d4c6189d7bdd0b6706963ddbb1dd7023bbe90c42e0e5901cc5aa315e45dce` |
| sdist | `dist/fan-out-20261110/sdk-artifacts/relf_agent-0.1.0a8+fanout.b4d9e82927e77bf2.tar.gz` |
| sdist SHA256 | `bb7699c3495e4c3fe1acd9a7fb9e6c312671c12996cc6d1f9c5d1657ba1e8247` |


源码基础版本仍为0.1.0a8，隔离构建副本使用唯一私有版本；仅init版本号按约定不同，安装产品与该副本相同。包内文档保留构建时的验收中快照，最终文字收尾不重建包。完整版本、公开main观察与各批入口见[当前交付](../../docs/current-delivery.md)，使用见[指南](../../docs/fan-out-workflows.md)。

原311份制品、35份非本批文件及封存原始证据SHA保持；未修改并行网站内容。最初pytest参数request触发收集错误、准确缺实现RED、初版授权夹具引用未导出异常类及其修正记录均保留；最终授权测试明确断言authorization_denied，不把较宽失败断言当授权证明。安装／Service没有用失败记录换门槛。原始结果位于 `dist/fan-out-20261110/`：各RED／GREEN、同ID定向XML、service/audit.json、production-result.json、compatibility.json和final-allowed/verification.json。机器索引见[本批记录](../../evals/results/relf-fan-out-20261110.json)。

本地提交以Git记录为准，单次跳过钩子，不推送或公开发布；原推荐组合、Alpha与所有历史失败保留。新平台、真实模型质量、活跃执行器故障、任意旧History／Session／Coding／部署或私有方法指纹迁移、外部采用、对等性能和完整M1／R01–R26仍未由本批验收。整体差距见[本轮对齐](2026-11-10-framework-alignment.md)。
