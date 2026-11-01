# 本地资料助手

一个使用现有 Relf-Agent SDK 的单 Agent 命令行示例：查询指定目录中的 UTF-8 Markdown／TXT，显示真实文件来源；生成 Markdown 报告，先展示完整正文和保存路径，明确批准后才创建文件。报告任务通过现有 CompletionVerifier 核对已提交的保存回执，普通文字说明不能代替完成报告；模型漏提保存时，在原决策预算内反馈继续，资料不足时明确失败且不保存。

程序、会话、执行记录和报告保存在本地。模型推理使用你显式配置的 API，服务会收到当前问题、必要的会话历史、工具说明和选中的资料摘录。资料目录应只放允许发送给该 API 的内容。搜索在本地执行；首版使用有界词法检索，不需要向量数据库。

应用发行名为 `relf-local-documents-example`，版本 `0.1.0`；Python 模块为 `local_documents`，命令为 `relf-docs`。本示例与 SDK 分别安装，应用逻辑不加入 SDK。

## 1. 从空目录安装

本轮选择的运行环境是 POSIX／Python 3.12。代码要求 Python 3.11 以上，但其他 Python 版本、Windows 和其他平台不因本说明取得验收资格。

准备同一份 SDK wheel 与完整的本示例目录。将下面两个绝对路径替换为收到的实际路径；也可以先将完整源码压缩副本解压，再把 `APP_SOURCE` 指向其中的 `examples/local_documents`。不要只复制 `src`，还需要本目录的配置、演示资料和包元数据。

```sh
SDK_WHEEL="/ABS/relf-agent/dist/public-preflight-fixes-20261030/private-artifacts/relf_agent-0.1.0a8+maintenance.0608576182db502f-py3-none-any.whl"
APP_SOURCE="/ABS/relf-agent/examples/local_documents"

mkdir relf-docs-demo
cd relf-docs-demo
python3.12 -m venv .venv
. .venv/bin/activate
```

核对 SDK 文件。这个命令在 macOS／Linux 均不依赖额外的 SHA 工具：

```sh
python - "$SDK_WHEEL" <<'PY'
import hashlib
import sys
from pathlib import Path
expected = "082b5ec9d1c107539b925d8a9f1332560eb7f92ec518b0e603ad02b5046cb482"
actual = hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
assert actual == expected, (actual, expected)
print("SDK SHA256 OK:", actual)
PY
```

先安装这份精确 SDK，再进行普通安装；不使用 editable 安装，不设置指向仓库的 `PYTHONPATH`。

```sh
python -m pip install "$SDK_WHEEL"
python -m pip install "$APP_SOURCE"
python -m pip check
python - <<'PY'
import importlib.metadata as m
import local_documents
import relf_agent
print("SDK:", m.version("relf-agent"), relf_agent.__file__)
print("App:", m.version("relf-local-documents-example"), local_documents.__file__)
assert m.version("relf-agent") == "0.1.0a8+maintenance.0608576182db502f"
assert m.version("relf-local-documents-example").split("+", 1)[0] == "0.1.0"
assert m.version("relf-local-documents-example") == local_documents.__version__
assert "site-packages" in local_documents.__file__
assert "site-packages" in relf_agent.__file__
PY
```

源码目录普通安装会构建应用包，并可能获取 Python 构建依赖。冻结交付时也可将第二条安装命令替换为收到的精确应用 wheel 路径，先按交付记录核对它的 SHA。SDK 仍使用上面原 wheel，不从索引寻找同名替代品，也不重建原 SDK。

复制本地运行材料，后续命令都在这个新目录执行：

```sh
cp "$APP_SOURCE/assistant.example.toml" assistant.toml
cp -R "$APP_SOURCE/demo-documents" demo-documents
```

## 2. 配置资料、输出和模型

`assistant.toml` 中的路径均相对于这个配置文件解析，运行前资料目录必须存在。三个根目录必须分离，不能相同或互相嵌套。

```toml
[paths]
documents = "demo-documents"
output = "reports"
state = ".assistant"

[model]
adapter = "deepseek"
name = "deepseek-flash"
base_url = "https://api.deepseek.com"
api_key_env = "DEEPSEEK_API_KEY"
timeout = 45
max_output_tokens = 2048
```

这里的型号是显式配置示例，需使用你的服务实际开放、支持文本工具调用和 JSON 输出的型号。另一个受支持的适配选项是 `adapter = "chat-completions"`，同时填写实际兼容端点、型号和密钥环境变量名；仅有兼容地址不保证该型号支持所需协议。

在当前 Bash／zsh 终端读入密钥，不将值写进 TOML 或运行记录：

```sh
printf 'Model API key: '
read -r -s DEEPSEEK_API_KEY
printf '\n'
export DEEPSEEK_API_KEY
```

首次接受任务会固定根目录和模型配置，保存在 `.assistant/config.json`；其中没有密钥值。执行库为 `.assistant/runs.sqlite`，会话引用位于 `.assistant/sessions/`。报告根及其原生写入回执也属于恢复材料，保留整个目录。

配置固定后，改变型号、端点、资料／报告／状态根或其他配置项，不能继续冒充原任务的环境。旧任务使用原配置、数据库、目录和代码恢复；新配置采用新的状态目录。不要删除配置记录、SQLite 或写回执来绕过不匹配检查。文件移动、原状态迁移和运行中的配置热更新不属于首版流程。

## 3. 查询、对话和真实来源

```sh
relf-docs --config assistant.toml --session main ask "Aurora 的 P1 告警多久确认？排查顺序是什么？" --command-id ask-aurora-1
relf-docs --config assistant.toml --session main ask "这个项目在重大事件结束后多久补齐复盘？" --command-id ask-aurora-2
relf-docs --config assistant.toml --session main history
```

使用演示资料成功回答时，应能核对到 `demo-documents/oncall.md` 中的“15 分钟内确认”和“24 小时内补齐复盘”，并显示实际读取的相对路径、行范围、完整文件 SHA256 和来源 ID。结果中的 `grounded=true` 只表示所声明引用已与本任务完成的读取回执对应，不代表应用证明了答案中每句话的语义正确性。

```sh
relf-docs --config assistant.toml --session main ask "资料记载 Aurora 的年度预算是多少？" --command-id ask-no-budget
```

演示资料没有预算信息，预期明确说明资料未提供，不编造金额或引用。没有依据的回答应为 `grounded=false`、空引用。应用拒绝不存在于本次任务读取回执中的来源 ID，不能把上一轮的引用 ID 直接当成本次文件证据。

交互对话：

```sh
relf-docs --config assistant.toml --session main chat
```

进入后直接输入问题；支持以下命令：

```text
/report summary.md 概括 Aurora 的值班和复盘流程
/status RUN_ID
/approve RUN_ID
/reject RUN_ID
/resume RUN_ID
/cancel RUN_ID
/history
/help
/quit
```

交互 `/approve`、`/reject` 显示原正文和路径，输入 `yes` 才提交决定，并恢复同一任务。普通 `/report` 或独立 `report` 命令不会自动批准。用相同 `--session` 和原配置重启程序后，会话继续保存在原 SQLite；模型每次只读取有界历史，不是无限上下文。`history` 最多展示 100 个 Turn。

**来源是读取时快照。** SHA 和行范围描述工具读取时的文件。随后修改文件不会回写旧回答或已批准报告，旧来源也不能代表现在的文件版本；需要当前内容时提交新的查询。

## 4. 报告预览、批准与跨进程恢复

```sh
relf-docs --config assistant.toml --session main report "根据资料总结 Aurora 的告警处理与复盘要求" --output aurora-summary.md --command-id report-aurora-1
```

有足够依据时，预期状态为 `waiting_approval`。输出包含原 Run ID、完整 Markdown、绝对保存路径、内容 SHA、Action ID 和摘要；Markdown 已包含确定性的“资料来源（读取时快照）”章节。此时 `reports/aurora-summary.md` **不存在**。

从预览原样复制三个值，不猜测 ID 或重新生成正文：

```sh
REPORT_RUN="原run_id"
REPORT_ACTION="原action_id"
REPORT_DIGEST="原digest"
APPROVAL_ID="approve:$REPORT_ACTION:$REPORT_DIGEST"

relf-docs --config assistant.toml status "$REPORT_RUN"
relf-docs --config assistant.toml approve "$REPORT_RUN" --action "$REPORT_ACTION" --digest "$REPORT_DIGEST" --command-id "$APPROVAL_ID"
```

只有核对正文、路径和来源后才输入 `yes`。独立 `approve` 命令**只持久记录原审批决定，不运行写入**。批准成功不等于报告已保存，此时文件仍应不存在。

退出整个终端程序，在一个新终端使用原目录、原配置和同一环境，重新激活 venv、注入同一个凭据环境变量，然后恢复原任务：

```sh
. .venv/bin/activate
relf-docs --config assistant.toml resume "$REPORT_RUN"
relf-docs --config assistant.toml status "$REPORT_RUN"
```

新终端需重新设置 `REPORT_RUN`，或直接把原 Run ID 写进命令；它不是会自动跨终端保存的 shell 变量。成功时状态为 `succeeded`，报告文件实际存在，并与预览正文相同。可以独立检查落盘 SHA：

```sh
python - <<'PY'
import hashlib
from pathlib import Path
p = Path("reports/aurora-summary.md")
print(p.resolve())
print(hashlib.sha256(p.read_bytes()).hexdigest())
print(p.read_text(encoding="utf-8"))
PY
```

新终端内也可用原值重设 `REPORT_ACTION`、`REPORT_DIGEST` 和 `APPROVAL_ID`，重复完全相同的批准命令，再重复原 `resume` 和 `report ... --command-id report-aurora-1`。预期找回同一个审批回执／Run，不再派发新模型任务或增加写入。用同一 command ID 改问题、报告名或参数会冲突。

`--yes` 可用于已审阅原预览的明确脚本批准，例如在上述批准命令末尾增加 `--yes`；它不绕过 action/digest 检查，也不能作为无人审阅时的默认行为。需要稳定机器输出时，在子命令前加 `--json`。本地所有命令选项都可用 `relf-docs --help` 及对应子命令的 `--help` 查看。

## 5. 拒绝、已有文件与取消

用一个独立会话演示拒绝，避免占用上面的会话：

```sh
relf-docs --config assistant.toml --session reject-demo report "概括 Aurora 的报告要求" --output rejected.md --command-id report-reject-1
```

复制这次新 Run ID 后执行：

```sh
relf-docs --config assistant.toml approve REJECT_RUN_ID --reject
relf-docs --config assistant.toml status REJECT_RUN_ID
relf-docs --config assistant.toml resume REJECT_RUN_ID
```

拒绝同样显示原预览并要求明确输入 `yes`。结果为原任务失败、`approval_rejected`，`reports/rejected.md` 不创建。`resume` 不会把已经拒绝的任务重新批准。一个批准／拒绝命令 ID 只属于原 Run／Action／摘要／决定，不要将它复用于另一份报告。

报告只创建输出根下的新 `.md` 文件，不接受子目录或覆盖。重复原已成功任务会找回原结果；**另一个新任务**提出已经存在的文件名属于冲突，不是覆盖或更新功能。需要新报告时使用新文件名，不删除旧回执制造“第一次写入”。

显式取消原任务：

```sh
relf-docs --config assistant.toml cancel RUN_ID
relf-docs --config assistant.toml status RUN_ID
```

交互中的 `/cancel RUN_ID` 使用同一控制。等待中的 Ctrl-C 会显式取消当前 Run，等待在途处理器结束后关闭资源，退出码为 130；这不是只取消一个观察协程。模型请求正在进行时，停止可能需等待它返回或原超时到达。取消不会撤销此前已经落盘的报告。

同一 Session 有待审批或其他未决任务时，不接受另一轮绕过它。根据提示先查询并批准、拒绝、恢复或取消**原 Run**；确认 Session 空闲后再提交新一轮。重复一个曾因 busy 被拒绝的 command ID 仍会找回原拒绝，新尝试使用新的 command ID。

## 6. 状态、故障与关闭

- `status` 和 `history` 只读原记录，不需要模型密钥，也不发送模型请求；仍需原配置和本地数据可读。没有接入过的会话没有历史引用。
- 缺少配置指定的密钥环境变量时，查询／报告命令会返回清楚的配置错误，不创建执行库。不要将密钥放进 TOML，或记录到验证材料中。
- 等待超时只结束观察，不取消原业务。保留 Run ID，查询状态后明确恢复或取消，不能把一个新的提交叫作恢复。
- 模型连接失败应保留实际错误和原任务，可能停在 `waiting_reconciliation`；不自动重发未知的模型调用或业务写入。示例的 `resume` 遇到未知模型结果只观察原状态，不再次发送模型请求。先查看 `status`，不要删除数据库、换配置或重复创建新任务掩盖失败。需要释放会话时明确取消原 Run，确认收口后再用新的 command ID 尝试；若仍不能收口，保留原状态供排障。
- 正常退出会排空 Runtime 的实际执行工作，保留稳定的待批任务，再关闭文件资源。若报告关闭未完成，保留原数据、原组件及错误；API 使用者应对原 Application 实例重试 `aclose()`，不要强行释放锁或销毁它继续创建第二个执行者。

## 首版固定限额与验证边界

| 项目 | 当前限额／语义 |
| --- | --- |
| 资料格式 | UTF-8 `.md`／`.txt`；根内路径检查，不读取越界路径 |
| 目录遍历 | 最多 128 个目录条目，目录计入；最多 8 层 |
| 单文件 | 最多 256 KiB；超限报错，不假装已完整读取 |
| 搜索 | 查询最多 500 字符；每次最多 4 段，每段最多 1600 字符 |
| 指定文件读取 | 每次最多 40 行，摘录仍受 1600 字符限制；标记截断 |
| 问题／模型上下文 | 问题最多 4000 字符；上下文上限 32000 字符；历史有界召回 |
| 单任务 | 最多 8 次模型决策、32 execution credits；不是货币费用上限 |
| 报告 | 普通 `.md` 文件名，最多 120 字符；正文含来源最多 128 KiB；仅新建 |
| 模型参数 | timeout 1–120 秒；max_output_tokens 128–4096；样例为 45 秒／2048 |

本地协议夹具、实际模型调用、隔离安装和独立开发者采用是不同证据。冻结应用使用 `0.1.0+local.<源码摘要>` 唯一版本，基版本仍为 `0.1.0`；应用和 SDK 的发行元数据必须与各自模块版本一致。准确 wheel／SHA 和真实成绩以该批次验证记录为准，不因 README 的存在就宣称通过全部门槛。本示例不扩展 R01–R26，不声称其他模型、平台、生产数据或任意资料的回答质量。

SDK 的当前交付及原有限支持范围见 [当前交付入口](../../docs/current-delivery.md)。本示例遵循 Apache-2.0；保留随附的 LICENSE 与 NOTICE。
