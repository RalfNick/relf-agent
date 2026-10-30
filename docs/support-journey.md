# 一个工单，逐步加入 Agent 能力

[文档目录](README.md) · [安装](installation.md) · [扩展方式](extending.md#先选择扩展方式)

本页的便捷生成入口面向[当前交付入口](current-delivery.md)，使用 `relf_agent` 导入和 `relf` 命令。先按[安装指南](installation.md)准备对应环境，再按[首用教程](getting-started.md)完成审批与恢复；随后在同一个生成项目中用工单 `INC-001` 学习组件组合。不新增 SDK 执行入口、模板种类或适配器。

使用历史公开 a2 包时，保留独立环境，改读[固定 a2 提交的原教程](https://github.com/RalfNick/relf-agent/blob/3a92720b63c5ac5aa27edc33a18b8d03396a81ff/docs/support-journey.md)，并下载[同一提交的原示例](https://github.com/RalfNick/relf-agent/blob/3a92720b63c5ac5aa27edc33a18b8d03396a81ff/examples/support_journey.py)。a1–a5 使用旧导入 `ralf_agent`，不能运行本页链接的 a6 示例；其他历史包使用各自归档内的教程和代码。不要通过给旧环境添加新模块来续跑旧 Run。

遇到错误时从[现象与下一步](recovery-guide.md#按现象定位下一步)定位。相同命令回读历史结果、观察超时后继续等待、恢复原匹配配置，是这条路径的共同规则。

## 从安装包生成同一个应用

安装本批推荐私有 wheel 后，从新目录的父目录执行：

```bash
relf init my-support
cd my-support
python -m agent_app.journey agent --command-id agent-1
```

默认 oncall 模板额外生成可编辑的 `agent_app/journey.py` 和 `agent_app/customize.py`，wheel 使用者无需下载仓库示例。原 `python -m agent_app` 仍是审批写操作教程，工厂与运行方式不变；可选 `journey` 使用只读工具，数据也分开。

本教程后续命令都在生成项目目录中执行。`journey.py` 使用安装好的 SDK 与标准库，内容与仓库 [support_journey.py](../examples/support_journey.py) 一致。已有项目不会自动改写；在新的空目录生成后比较应用代码，保留原版本供历史 Run 恢复。

原 a6–a8 没有这两个生成文件，可继续使用[固定 a6 原示例](https://github.com/RalfNick/relf-agent/blob/ba1c81fca67e15e70c1d51d0f4ecbbbcbbb37239/examples/support_journey.py)及对应教程，按 `python support_journey.py ...` 运行。本批候选的安装成绩不授予旧包。

所有步骤使用同一工单与只读 Python 工具；不同阶段使用独立 SQLite 文件，避免把新定义或配置用于旧 Run／Session。默认目录 `.ralf/support-journey/` 保存执行记录、Session、知识和 Facts，不需要额外数据库服务。

| 阶段 | 增加的现有能力 | 主要代码 |
| --- | --- | --- |
| `agent` | Provider＋Python 工具＋单 Agent | `provider_for`、`tools_for`、`AgentSpec` |
| `session` | 持久 Session 与跨进程 Turn | `agent.open_session`、`session.submit` |
| `rag` | 本地文档与词法检索 | `SQLiteKnowledgeStore`、`KnowledgeContext` |
| `memory` | 显式长期 Facts 与召回 | `SQLiteMemory.put_fact`、`MemoryRecallPolicy` |
| `workflow` | 先诊断、后整理答复的顺序编排 | `WorkflowSpec` |

## 1. 离线 Agent 与自己的工具

```bash
python -m agent_app.journey agent --command-id agent-1
python -m agent_app.journey agent --command-id agent-1
```

第一条应得到 `succeeded`、工单状态和 `model_calls: 2`。第二条找回相同 Run／结果，`model_calls: 0`。离线 Provider 复制测试数据和引用，仅证明执行与装配，不代表模型推理或诊断质量。

修改 `tools_for` 中的 `lookup_ticket` 可接入自己的只读业务查询。此例仅提供 `INC-001`。写工具仍需要原效果类别、审批和核验契约，按[工具 SDK](sdk-model-tools.md)接入；不要直接把只读声明改成生产写操作。

## 2. 同一应用显式接入真实模型

先用自己的凭据管理方式提供 `DEEPSEEK_API_KEY`，再将占位型号换为账户支持的实际值：

```bash
python -m agent_app.journey agent --provider deepseek-chat --model YOUR_MODEL --data-dir .ralf/support-live --command-id live-1
```

也可选择 `--provider chat-completions`，使用 `OPENAI_API_KEY` 与对应型号。缺少配置时明确失败，不降级为离线结果；真实调用可能收费。其他协议继续使用[已有 Provider](model-adapters.md)，在 `provider_for` 中替换即可。

真实与离线运行分开数据目录。更换模型、指令或工具后使用新命令／Session；保留原配置用于恢复历史任务。后续命令默认仍使用离线 Provider，也可以显式选择同一真实模型。本轮安装验证没有调用在线模型，不增加线上型号兼容或质量结论。

## 3. 跨进程继续同一个 Session

```bash
python -m agent_app.journey session --command-id turn-1
python -m agent_app.journey session --command-id turn-2 --input 'What should we check next?'
```

两条命令是不同进程，使用同一 `INC-001` Session。第二次结果中的 `session_records` 应大于零，表示已有保存记录进入当前模型上下文；它不是语义记忆质量评分。相同命令重复执行返回原回执。

先完成或处理原 Turn，才能提交下一 Turn。此例只有有限只读工具；需要审批的应用沿用[首用教程](getting-started.md)，不要通过新建 Run 绕过 busy 或未知效果。

## 4. 加入本地 RAG

```bash
python -m agent_app.journey rag --command-id rag-1
```

结果的 `knowledge` 应包含 `cache-recovery`、文档版本和 `local://runbooks/cache-recovery`。这是 SQLite 内的来源标识，不是远程请求。示例以创建 CAS 导入一条运维手册，已有版本、已删除来源不会被启动过程覆盖或复活。

当前使用词法检索，不下载 Embedding。要接入已有语义检索服务，替换 Knowledge／Retriever 组合即可，参考[混合检索](hybrid-retrieval.md)；不要把词法命中当成语义质量。

## 5. 加入显式长期 Facts

```bash
python -m agent_app.journey memory --command-id memory-1
python -m agent_app.journey memory --command-id memory-2
```

示例由可信宿主首次写入 `support` namespace 下的 `response-style=concise`，结果的 `facts` 展示实际召回值。重启不覆盖已有值；namespace 与 Agent 名称对应，不能把别人的记忆传入当前 Scope。

这里演示显式写入与持久召回，**没有自动提炼、冲突修订或遗忘**。若需要已有的自动提炼，请显式选择[受管理记忆](managed-memory.md)，配置来源字段 allowlist；不要把模型声称的内容直接当作已核验事实。

## 6. 复用这些组件组成 Workflow

```bash
python -m agent_app.journey workflow --command-id workflow-1
```

`WorkflowSpec` 先运行 `triage`，再由 `support` 整理答复；前一步输出成为后一步输入。模型、工具、知识和 Facts 沿用前面的装配方式，工具仍全部只读。默认离线结果证明两个步骤可以执行，不代表真实规划、团队协作或通用业务正确性。

## 继续定制与恢复

先运行已生成的替换示例：

```bash
python -m agent_app.customize agent --data-dir .ralf/my-support --command-id custom-1
python -m agent_app.customize agent --data-dir .ralf/my-support --command-id custom-1
```

两次返回同一 Run 和结果；其中 `source=custom-model`、`ticket.source=custom-lookup` 表示实际使用了替换组件。`model_calls=null` 表示这个 Provider 没有声明计数接口，不是零调用，也不是模型质量评分。

| 修改位置 | 复用的 SDK 契约 | 默认与替换 |
| --- | --- | --- |
| `SupportModel.complete`／`provider_for` | 普通异步 ModelProvider，返回 ModelResponse，工具仍由 Engine 派发 | 离线自定义 Provider 可直接运行；真实模型在 journey 中用已有 `--provider/--model`，或显式注入已有 Provider |
| `custom_tools()` | ToolRegistry 的异步 Python 工具、推导 Schema 和明确效果类别 | 改 `lookup_ticket` 的只读业务查询；写入须另行声明审批、幂等／核验契约 |
| `memory_for_example()` | 同步或异步的 Session／Facts 后端 | 默认 `None` 沿用持久 SQLite；`ephemeral=True` 选择已有 InMemoryMemory，仅适用于一次进程内的临时实验 |

可编辑应用的 `main(argv=None, *, provider=None, tools=None, memory=None)` 提供上述三个注入位置，**不是新的 SDK 公共端口**。显式注入 Provider 时，不同时传 `--provider/--model`，避免一份配置悄悄覆盖另一份。`None` 才选择默认值；传空工具表不会补回默认工具。

注入对象由调用方持有；Runtime 只拥有示例的 Engine。带客户端的适配器应在同一事件循环上由自己的宿主生命周期创建、等待和关闭，不能将同步 `main()` 当作异步宿主容器；异步应用使用示例的 `run()` 或直接使用已有 Runtime。初始化 Facts 会等待同步／异步端口的实际结果；它是可信宿主首次种入演示偏好，不是模型自动记忆。

这里的 `memory` 是同时提供 Session 和 Facts 方法的组合对象；`memory`／`workflow` 阶段首次种入偏好还需要 `inspect_fact`。该检查方法超出最小 Facts 端口，不表示所有仅实现 `facts/put_fact` 的后端都能直接用于这个应用。SQLiteMemory、InMemoryMemory 及相应的 ThreadedMemoryAdapter 示例满足此要求；要分开两种存储，使用已有 LocalEngine 的独立注入位置。

使用 InMemoryMemory 时选择新的数据目录和命令，仅在持有同一个对象的进程内保留数据。下一进程不能恢复它的 Session 或原后端身份；持久 SQLite 才是本教程的恢复默认。替换远程后端的正式契约见[记忆适配](session-adapter-contracts.md)，不因示例可注入就取得真实服务资格。

- 替换模型：`provider_for`；替换业务接口：`tools_for`。
- 替换知识／记忆：`run` 中注入相应端口，保留 Scope、namespace、CAS 和来源校验。
- 改为图、Plan／Team：使用[已有编排定义](orchestration.md)，另开配置与数据目录，按所选组合验证。
- 进程重启后，以相同文件、原数据目录、原阶段和原命令继续原任务。配置变化不是恢复；观察和取消规则见[Agent API](agent-api.md)。

示例共用一个 SQLite 连接，Knowledge／Memory 借用它，Runtime 拥有 Engine 并负责排空后关闭。遇到 `CloseIncomplete` 时保留原资源并按[恢复指南](recovery-guide.md)处理，不能强制释放租约。Temporal／Coding、函数指纹专项和 S2 不在本教程验收范围。

## 选择入口与排障

| 需求 | 已有入口 |
| --- | --- |
| 一个模型和少量工具 | [Agent](agent-api.md) 便捷入口，不必先理解 Profile 与所有数据端口 |
| 同一应用共享 Session、知识和记忆 | 本教程的 Runtime＋LocalEngine，或已有推荐组合 |
| 用 JSON／TOML 选择版本配置与组件工厂 | [现有 config 模板／RuntimeProfile](runtime-assembly.md)，先声明 Profile，再保留旧版本用于恢复；不新增配置层 |

| 现象 | 下一步 |
| --- | --- |
| 生成后没有 `journey.py` | 核对 `python -m pip show relf-agent` 与本批精确版本；旧包不通过复制内部模块升级 |
| 实际模型配置返回 `validation_error` | 核对型号、协议和凭据环境变量；不会退回离线结果，生成模板本身不调用收费模型 |
| 替换组件后 `definition_mismatch` | 原任务继续使用原代码／配置／后端；新配置另用数据目录，不移除身份检查 |
| Session busy | 先按[Session API](session-api.md)找到原 Turn，处理其审批／未知效果；不通过新 Session 绕过 |
| 等待超时但状态还在运行 | 超时只结束观察；继续等待或显式取消业务，按[等待语义](agent-api.md)操作 |
| `CloseIncomplete` | 关闭未完成，原资源仍有义务；在仍持有 Runtime 的宿主中重试关闭，不强制释放连接或租约 |

`relf --db .ralf/support-journey/agent.sqlite --format text inspect RUN_ID` 可只读查看默认 Scope 的原事实。需要继续业务时使用原程序与原命令；不要用默认 CLI 工厂接管自定义应用。生成项目中的原 oncall 审批流程则继续使用其 `agent_app.runtime:create_engine` 工厂。
