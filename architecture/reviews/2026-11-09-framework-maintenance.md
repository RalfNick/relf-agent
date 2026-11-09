# Local 节点与检索公共边界维护

日期：2026-11-09。基线 `ec23ae507b7c9147611722d544e7c05ad5cb2eab`。本轮仅修复已有公共契约，不扩展编排、模型、工具或后端。

## 已确认问题

- Local 节点提交后替换注册表 `validate_output`，同一 Release 的整数输出 Schema 可被绕过，非法字符串仍得到成功。正常对照为 `validation_error`。修复沿用 Temporal 已有六公共端口固定，运行期间漂移明确拒绝。
- VectorRetriever 逐个异步回读来源时，第二项等待可跨过第一项 TTL，直接结果和 KnowledgeContext.references 仍含已过期项。正常 Engine 随后的 validate 有保护；本轮不声称已证明模型使用了过期内容。修复只复用现有最终选中项 TTL 校验，不新增来源 I/O。

## 设计与证据

见[设计](../../docs/superpowers/specs/2026-11-09-framework-maintenance-design.md)、[计划](../../docs/superpowers/plans/2026-11-09-framework-maintenance.md)。原独立复现及 RED／GREEN 记录保存在 `dist/framework-maintenance-20261109/`；定位脚本另在 `dist/execution-followup-review-20261109/` 和 `dist/data-followup-20261109/`，不覆盖历史文件。

源码仍为 `0.1.0a8`；隔离构建副本固定为 `0.1.0a8+guards.34d5fe53e3fe66ef`。464产品、1580代码／测试输入已固定；wheel SHA-256 为 `bce93dd4312ffb61f182016add8b6628d7ba7ccbac261f8acdb2e52761fafe84`，sdist 为 `760d9bd723a806b1a8ac3f2f354918586e175f54028e7ef82c55a46486c9b8f6`。这只是本地私有验证包，不替换推荐组合。

| 检查 | 实际结果 | 范围 |
| --- | --- | --- |
| Local 新回归 | 22通过 | 六入口提交后／await期间漂移、串并行SQLite原回执恢复、初始自定义与未选路径 |
| Retrieval 新回归 | 11通过 | 异步跨TTL、到期相等、永久／有效来源、预算排除、无额外读取和显式新查询 |
| 源码受影响集合 | 33模块603通过、0跳过 | 含节点／知识恢复、配置、契约及Temporal离线状态 |
| 目录外准确wheel同组 | 同603个ID全部通过、0跳过 | 包含独立starter构建夹具；framework导入仍在新site-packages |
| 纯运行依赖 | 10条命令通过 | 独立无pytest／Temporal环境，真实Local图、漂移拒绝、过期引用拒绝及显式新读取 |
| sdist与starter重建 | 各464产品字节一致 | 构建容器SHA可不同，产品逐项比对 |
| 所选元数据兼容 | 通过 | 上批准确capacity包、本批源码／安装的Local Agent／节点、普通Temporal、检索身份与8catalog |
| 完整离线回归 | 15718通过、913条件跳过，零失败／错误 | 共16631项；同一冻结输入、原10秒恢复子进程和7200秒整体看门狗 |

准确XML、命令、分层结果与哈希见[机器记录](../../evals/results/relf-framework-maintenance-20261109.json)。完整轮自然退出0，JUnit2347.255秒、runner2351.459秒；原16598个ID及其状态保持，新增33项全部通过，源码／安装同603项也在完整轮内全部通过。913条件跳过不计为实际服务／模型通过，不增加这些资格。

五个原10秒编排崩溃窗口及两项连接关闭检查通过，原崩溃／恢复trace终点完整。pytest、fixture guard及其关联PID／PGID在本轮结束后查无残留，外层guard已回收；只对本轮查询对象作此结论。464产品／1580输入、308原制品、89份本轮封存阶段文件和28份上批完整轮证据SHA保持。原失败和夹具修正均保留，本轮限定范围按这些实际证据收口。

版本替换仅发生在隔离构建副本；包内文档为构建时快照，最终验收文档与原包分开保存，不重写固定制品。本地提交以Git记录为准，不推送或公开发布。

## 恢复与失败记录

Local准确基线RED为20失败／2通过；最初两次新测试GREEN尝试分别有18和4个夹具预期错误，涉及默认budget、原drive返回failed而非抛出、以及对内部post-await检查的过强零调用断言。只修测试以符合原契约，未改变预算、异常或状态机；全部原日志保留。最终测试覆盖的处理器执行中漂移且回执已保存的场景返回原 `failed/definition_mismatch`，SQLite已接收回执仍保存；尚未确认效果的路径保持原unknown核验，不据此推断未执行。重开只采纳／结算原Action，failed终态保持，业务调用总计一次，不把恢复说成重新成功运行。

TTL基线RED为6失败／5通过。原RED外壳末尾为tail命令，不能用其外壳状态0当作测试通过；原pytest摘要和XML明确记录失败，GREEN及同组原始退出码另行记录。修复不增加来源I/O，也不把原Engine后续已有保护描述为失效。

准确安装首轮为600通过／3个setup错误：旧RAG starter夹具现场执行 `python -m build --no-isolation`，而测试环境缺少build工具及构建输入。保留原XML／exit1记录；只向该目录外测试环境补显式已安装的build／setuptools／pyproject_hooks分发文件和固定构建输入，不下载，不修改测试／产品字节。pytest.ini保持无src注入，framework导入确认仍为候选site-packages；原夹具重建wheel的464产品与准确候选相同。新标签同603项通过。纯运行依赖资格由另一个不含这些开发工具的环境单独验证。

## 范围

端口固定仅覆盖声明的公共入口与原组件身份，不递归固定任意私有函数、闭包或外部依赖。TTL 只按返回边界的已知时间复核，不保证返回后有效，也不提供跨数据库原子快照、自动刷新或重新索引。

原审批、预算、Action、持久化回执与未知效果继续由原 Local／Temporal 权威处理。旧任务保留原包／匹配宿主；不据此授予任意旧发布迁移、更多平台／模型／服务或完整 R01–R26 资格。

原推荐组合、原 Alpha 与全部历史失败保留；网站并行修改不在本轮范围。验证后仅本地提交，单次跳过钩子，不推送或公开发布。
