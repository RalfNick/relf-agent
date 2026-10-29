# 安装后连续上手与组件替换

本批是第二阶段的开发体验交付，范围为一个已安装应用：Agent → Session → 本地词法 RAG → 显式 Facts → 顺序 Workflow，并能替换模型、异步 Python 工具和借用记忆。复用现有默认 oncall starter，不新增模板、后端、适配器、节点拓扑或 SDK 抽象。

## 唯一推荐本地制品

| 项目 | 值 |
| --- | --- |
| 版本 | `0.1.0a8+maintenance.709bc187e50d4956` |
| wheel | `dist/support-journey-20261029/private-artifacts/relf_agent-0.1.0a8+maintenance.709bc187e50d4956-py3-none-any.whl` |
| SHA256 | `78e874a62a3d80f77c003ec0ffbaa8f72ad9df4d4a2cf149fe78fc3142ce2659` |
| 产品范围 | 450 文件；相对第一批仅 starter 更新、增加两份应用源文件，执行内核不变 |

这是本地私有安装候选，尚非公开发行或新平台资格。第一批 `349fff` 私有包、原 a8／a7 及全部历史失败保留。原包不自动增加新模板文件；已有应用不会被生成器改写。

```sh
python -m venv /tmp/relf-support-app
/tmp/relf-support-app/bin/python -m pip install dist/support-journey-20261029/private-artifacts/relf_agent-0.1.0a8+maintenance.709bc187e50d4956-py3-none-any.whl
/tmp/relf-support-app/bin/relf init /tmp/my-support-project
cd /tmp/my-support-project
/tmp/relf-support-app/bin/python -m agent_app.journey agent --command-id first
/tmp/relf-support-app/bin/python -m agent_app.journey session --command-id turn-1
/tmp/relf-support-app/bin/python -m agent_app.journey session --command-id turn-2
/tmp/relf-support-app/bin/python -m agent_app.customize agent --data-dir .ralf/custom --command-id custom-1
```

完整分步操作、实际模型配置和排障见[连续教程](../../docs/support-journey.md)。不用下载仓库示例，也不用配置框架源码路径。

## 行为与边界

- 生成的 `journey.py` 是可编辑应用源码，与仓库示例字节一致；`customize.py` 提供普通 Provider、异步 Python lookup 和显式临时记忆选择。
- 三个应用注入位置不改变 SDK 端口。只有 `None` 选择默认；任意 Provider 不要求 `.calls`，结果中的 null 不表示零调用。
- 外部对象保持借用所有权；默认仍为 SQLite，InMemoryMemory 仅用于保留同一实例的进程内实验。该组合记忆对象需提供 Session＋Facts，种入演示偏好还需 `inspect_fact`。
- 同步和异步的记忆检查／写入都等待完成。线程桥测试证明实际调用的是既有 ThreadedMemoryAdapter，不以协程对象当作结果。
- 原 oncall 的审批写入、效果核验和恢复工厂不变；其他模板不增加示例文件。Profile 继续使用原 config 模板和显式工厂，不引入新配置解释器。
- 没有修改执行权威、Action、审批、取消或未知效果契约；不恢复暂存的 Temporal 直接 Tool 节点探索。

## 验证记录

原始证据位于 `dist/support-journey-20261029/`。基础路径 11 项先通过；新增注入位置 5 项有效失败后通过，模板导出有效 RED 先确认缺文件；首轮导出测试的错误 import 与后续有效 RED 分开保留。原五阶段、生成项目和定制案例初步组合 35 项通过。

只读审查发现异步 Facts 初始化缺少等待：既有 ThreadedMemoryAdapter 复现 1 failed／1 error（`-W error`）。修复仅在应用初始化等待同步／异步结果；相关 5 项通过。审查后没有未关闭的重要问题，组合记忆的额外检查要求已在文档明确。

最终源码与独立安装各 **92 passed**，均 `-W error`、无失败／跳过，控制台耗时分别137.19s／132.09s。11个相关模块包括五阶段应用、替换位置、跨进程 Session、默认 starter 审批和业务已提交后崩溃恢复、重复控制与既有 Profile／Builder。安装夹具仅复用上述精确私有 wheel，每个测试及断言与源码相同，不在安装测试中另建同版本 Alpha。

主任务与独立只读审查分别比对全部28种模板：27种完全相同，oncall 仅 README 与两份新增应用文件不同，原审批 runtime 字节不变。新私有包450产品文件逐项核对，安装模块来自仓库外 site-packages，没有源码目录／PYTHONPATH 注入。

另从安装 CLI 实际生成项目并执行文档中的11条命令，验证重复提交模型调用为0、Session跨进程续接、定制工具实际输出和只读 inspect。首次脚本混用了缓冲 readline／communicate，丢失 inspect 后续文本而断言失败；产品命令均成功，夹具改为无缓冲捕获，原目录／诊断／失败记录保留，未修改产品或放宽断言。

本次仅在 macOS15.6.1／ARM64、Python3.12.7 执行。记录了项目生成、首条标准输出／总耗时、子进程 CPU 与峰值内存，原始数据为 `doc-smoke.json`；首条标准输出是最终 JSON，不是模型首段。内部轮询次数未量测，只有显式 CLI inspect 计数，不据此宣称性能提升或完整性能门槛。

本批不请求真实模型、Embedding、Redis／PG／Temporal 服务；第一批未变的执行内核证据复用，不增加新包平台资格、真实任务质量或外部采用结论。

最终静态与冻结核对：Ruff、1484文件格式和 Git 空白检查通过；888个本地文档链接有效。原 a7／a8 两包及清单、第一批私有 wheel 共7个保护文件哈希不变。450产品逐项匹配安装内容（仅私有构建版本后缀按规则归一）；原448文件中447个未改，仅 starter 变化，另外增加两份应用资产。

## 剩余工作与下一批

本批只收口连续应用路径。受管理异步节点继续先复用现有有限 Tool 节点，按实际需要另批验收；不自动推进新后端、循环、reducer 或共享状态。随后才以固定最终配置验收单 Agent、语义 RAG、Plan／Team 的业务质量、引用、恢复、耗时和用量；外部开发者采用与对等框架比较单独记录。
