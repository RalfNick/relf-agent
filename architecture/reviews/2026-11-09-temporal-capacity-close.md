# Temporal 容量背压与关闭诊断验收

日期：2026-11-09。基线 `4bb46fe7a8935e6d13962a6c34e02519122c4c53`。本轮仅维护默认Temporal节点容量、关闭诊断及交付入口；不增加执行权威或其他能力，不推送、触发远端CI或公开发布。

## 实现范围

- 新默认节点owner显式发布 `workflow-node-capacity-owner`／`workflow-node-capacity-1`，执行16槽、结束通知256槽保持。仅可证明未启动的满额拒绝交原Native History有界timer；同一Action／attempt／effect_key和预算预留保持，用transport ordinal固定请求摘要并fence迟到准入。
- 每Action最多64次拒绝、0.1秒指数增长至1秒，容量与实际执行共用原schedule_to_close窗口；每次Activity保留原timeout与剩余总窗。未知、foreign claim、重复、关闭和业务异常不能作为容量重试。
- 单独History timer Task和无timeout条件等待隔离查询激活；只有定时器实际完成或终态才能推进。新容量协议的ACK活动ID使用原Action内持久序号，不依赖事件日志长度。旧普通／显式原owner分支保持原路径。
- `CloseIncomplete`原code、message和report对象保持，新增只读、脱敏诊断快照；固定阶段、权威、所有权和真实计数，未知不猜。CLI仅对该异常及RuntimeBuildError直接包装的该cause附加诊断，原取消／关闭顺序及同实例重试保持。
- 交付入口简表区分原推荐组合、已推开发源码、main、本轮验证包和官网资格，原包／SHA／失败保留。外部网站工作区改动不属于本轮。

设计和计划见[容量设计](../../docs/superpowers/specs/2026-11-09-temporal-node-capacity-design.md)、[容量计划](../../docs/superpowers/plans/2026-11-09-temporal-node-capacity.md)、[关闭诊断设计](../../docs/superpowers/specs/2026-11-09-close-diagnostics-design.md)。使用见[Temporal节点](../../docs/temporal-managed-nodes.md)和[关闭诊断](../../docs/close-diagnostics.md)。

## 验证状态

本轮源码仍为 `0.1.0a8`。仅在隔离构建副本生成唯一验证版本 `0.1.0a8+capacity.c5a29d8fa601a9ec`，不是新公开版本，也不替换原推荐包。464个产品文件和1578个代码／测试输入固定后，按同一快照完成下列检查。

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| 源码受影响回归 | 884通过、0跳过，52.41秒 | 46个模块 |
| 隔离wheel受影响回归 | 同884项通过、0跳过，56.58秒 | checkout外运行、准确候选 |
| 源码真实Temporal Service | 5通过、0跳过，95.17秒 | 容量等待、取消、重启、关闭／ACK |
| 隔离wheel真实Service | 同5项通过、0跳过，89.25秒 | 准确候选，同一原期限 |
| 仅运行依赖与sdist | 16条命令通过；重建464产品字节一致 | 无pytest／Temporal的基础环境、CLI诊断／同实例重试 |
| 所选兼容检查 | 通过 | 普通Temporal发布、明确旧节点owner、原通知身份／Context固定方法及7个目录摘要 |
| 完整离线回归 | 15685通过、913条件跳过，零失败／错误，2438.285秒 | 同一冻结输入、原恢复期限；原16490个ID无删除 |

定向与Service耗时按pytest结束摘要；完整轮按JUnit计时，runner总耗时2441.505秒。机器记录分别保留原JUnit与runner数值，不把不同计时边界作性能对比。

wheel SHA-256：`5536d856fa3b91bbb12c85a094ce6e928077ca4c4a3bf1d01b7c747d5b4ad918`；sdist：`506ba759b648dbb3c77e3f8304c4a7fc3a77111608007d1e70202c5c3afe9d2d`。sdist重建包容器SHA可不同，464产品字节已逐项比对。原306份wheel／sdist哈希、受保护旧审查和持久hooks配置均保持。

原始XML、Service日志／History、制品清单和运行命令在 `dist/temporal-capacity-close-20261109/`；可追踪摘要见[机器记录](../../evals/results/relf-temporal-capacity-close-20261109.json)。本轮限定范围已通过验收：原15582个通过ID继续通过，新增108个ID保留；本批884项也在完整轮内全部通过。913条跳过包含本批5条真实Service用例，它们的服务资格以单独源码／安装5/5为准，不计为离线通过。五个原编排崩溃窗口继续使用每子进程10秒，实际调用约1.8–2.0秒，崩溃／恢复轨迹终点和两项连接关闭检查独立核对通过。

完整轮自然退出，pytest、原fixture guard及其进程组在结束后核对无残留；冻结产品／输入和原证据哈希保持。仅对这次原进程组作此结论，不扩展为所有宿主进程或执行Worker全冷恢复资格。Ruff／格式、空白及本轮文档链接另按提交前记录核对。最终文档记录与制品内构建时文档快照分开，固定包不重写；本地提交以Git为准，不推送或公开发布。

## 保留的失败与定位

原16槽复现在本轮独立目录再次确认，第17个无业务启动但child failed；原文件未覆盖。独立审查补出了no-start重复回执、unknown不能被后续未派发声明修复、终态迟到证明、guard取消／关闭、timer ready取消、外层256通知满额等反例；所有RED和阶段green分别保存。

真实Service首轮因父History子任务意图先于子Workflow建立而遇NotFound，夹具只在原30秒就绪窗口重试缺失，未延长期限。第一轮5项矩阵为4通过／1冷重放失败：原timer已fired，冷重建却多记一个timer；SDK查询激活更新时钟并排空已ready协程，结合原History／离线时钟trace推断手工绝对retry_at判断受查询激活影响。改用明确的History timer完成后，冷重放继续暴露ACK ID依赖日志长度（实际5、重放6）；新协议改用原Action序号，另有真实RED／green。原两份不确定性History仍保留，不能把新原型的修复视为对这些未发行坏History的透明兼容。

首次完整回归在受限沙箱运行，确认8条localhost绑定EPERM；另14条supervisor ready握手不匹配，具体成因未独立证实。保留全部22条原失败／错误，以原PID受控终止，原runner记录exit -15、221.995秒，核对该原进程组已退出。这是中止的部分轮次，不能作为完整回归成绩，也不能把全部22条都断言为沙箱问题。后续在允许本地监听的权限下，以同一产品／测试／期限独立重跑，22个对应ID均通过；原日志和分类不覆盖，也不倒推首轮14条的唯一原因。

证据均在 `dist/temporal-capacity-close-20261109/`；早期定向／单例Service成绩不代签最终冻结包与整轮。源产品已固定464文件、输入1578文件；若后续实现变化须另记新制品，不能覆盖原包。

## 资格边界

本批macOS ARM64／Python3.12，真实Service使用已缓存Temporal CLI1.9.1／Server1.32.0及SDK1.34.0，无下载、模型或远程业务。History Worker冷重启保留独立Activity Worker及实际处理器；不冒充物理执行Worker全冷恢复。写效果与任意远端存储、其他平台、模型质量、独立采用及完整R项不由此授予。

旧节点、Coding／部署等所选发布固定源码／方法指纹；旧任务继续保留原包及匹配Worker，不降低漂移保护。原普通发布和明确旧owner兼容另行逐项核对。完整R01–R26、其他未选节点组合保持开放。
