# Framework 接入边界维护验收

日期：2026-11-05。源码基线 `e317a48`；本轮修复已有能力，保留原制品和失败，不推送或公开发布。

## 范围

- Schema 统一使用无外部检索 Registry；已声明的固定本地资源仍可解析。
- 节点保持 input/config 独立引用根，提前拒绝冲突资源 ID。
- Embedding 运行／递归解析异常统一脱敏 ProviderError，取消仍传播。
- 资料助手只转换 shlex 解析失败，继续原聊天；业务异常不被吞掉。

Local／Temporal 保持原执行权威；没有新增后端、循环、流式 Workflow 或多模态。实际能力差距见[本次对比](2026-11-05-framework-alignment.md)。

## 当前验证记录

| 验证 | 实际结果与范围 |
| --- | --- |
| Schema 边界 | 20 个真实 RED 后，55 项通过；含 `$ref/$dynamicRef` 无检索、局部定义、命名嵌入资源、业务字面量及无界递归错误 |
| 节点 | 局部引用 7 个 RED、冲突资源 2 个 RED 和相对资源根反例保留；8 模块170项通过，包含原进程崩溃窗口与新增审批／重开／重复不重写 |
| Embedding／聊天 | 5 个真实 RED 后，3 模块46项通过；首次沙箱端口拒绝另留，既有取消和资源所有权回归保持 |
| 完整源码 | **15397 passed、895 skipped、零失败／错误**，2792.06秒；16292项，新增78项、原ID零删除；1529个代码／测试／工具输入与8个应用输入未变 |
| 准确安装 | SDK与应用均从目录外 site-packages导入；60模块 **1344 passed、零跳过**，218.52秒，与源码整轮中的相同ID均通过；无checkout的SDK／应用源码或PYTHONPATH |
| 仅运行依赖 | wheel／sdist重建、SDK核心运行及两CLI共14条检查通过；无pytest／Temporal依赖；456个SDK产品和应用模块重建内容一致 |
| 独立审查 | 未发现新增P1／P2；独立143项通过。另9项曾因只读沙箱禁止回环端口在夹具阶段失败，主线程获准的安装与整轮已覆盖通过，未将环境失败删去 |
| 原10秒窗口 | 五窗口在完整轮内全过，每例含崩溃／恢复约2.53–2.73秒；单子进程期限仍10秒，父进程FD均44。保活回收，整轮无睡眠／唤醒，未放宽原期限 |
| 完整性 | 原296个制品、旧失败XML及用户未跟踪审查文件哈希保持；没有改变原a8版本或依赖 |

[机器记录](../../evals/results/relf-framework-boundaries-20261105.json)保存精确来源与结果。原始日志保存在忽略目录 `dist/competitor-gap-review-20261105/`；独立审查的沙箱失败、节点旧源码对比控制器首轮路径错误和各RED均按原范围保留，不拼接为额外全库资格。895项按原条件跳过主要依赖实际服务／平台配置；没有真实模型或外部服务成绩。

## 准确验证制品

仅为本轮目录外安装验证构建，不替换[原推荐组合](../../docs/current-delivery.md#原推荐组合与来源)，不是新Alpha。源码基础版本仍是0.1.0a8；隔离构建副本设置唯一私有版本和应用精确SDK依赖，原制品不重建。

| 制品 | 准确值 |
| --- | --- |
| SDK | `0.1.0a8+boundaries.78b549d7aed371da` |
| SDK wheel | `dist/competitor-gap-review-20261105/sdk-artifacts/relf_agent-0.1.0a8+boundaries.78b549d7aed371da-py3-none-any.whl` |
| wheel SHA256 | `a62deac382b25bf86474be8977752fa5646c6299991f35683663618668bd1f78` |
| SDK sdist | `dist/competitor-gap-review-20261105/sdk-artifacts/relf_agent-0.1.0a8+boundaries.78b549d7aed371da.tar.gz` |
| sdist SHA256 | `10497124280f8f7c6c644bd86581f49cc1e3263d935fe71641b3f22e1160887b` |
| 应用 | `0.1.0+boundaries.4e3760eff46012dd` |
| 应用 wheel | `dist/competitor-gap-review-20261105/application-artifacts/relf_local_documents_example-0.1.0+boundaries.4e3760eff46012dd-py3-none-any.whl` |
| 应用 wheel SHA256 | `e689cf79dbfd0c47ecc3f3f9c6f553103bdd696add7d4082fca22f4081b8023c` |
| 应用 sdist | `dist/competitor-gap-review-20261105/application-artifacts/relf_local_documents_example-0.1.0+boundaries.4e3760eff46012dd.tar.gz` |
| 应用 sdist SHA256 | `69083ed55c742f7d12c6238b8e6cf72b7229a27b5f2ebbf3137b79f1c8759a04` |

包内文档为构建时快照；最终验收与兼容说明以本记录和当前文档为准，不覆盖已冻结包。没有推送、远端CI、官网部署或公开发行。

## 兼容边界

无引用节点的完整旧新 Registry／Tool Manifest 已独立核对；含引用的包装修复及 typed 工具参数校验代码会改变相应身份。原 Run 需要原包／代码／配置，不提供透明迁移，不关闭任何完整 R 项或平台／真实模型资格。详见[Schema 指南](../../docs/schema-validation.md)。

本轮只认证列明的运行校验／安装边界；评测专用Oracle、第三方插件、其他实际服务／平台和新旧包通用迁移仍需各自验证。完整M1／R01–R26及对等质量未由此验收。
