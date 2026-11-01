# 本地资料助手首版设计

依据：用户当前目标与 `docs/current-delivery.md` 的本地示例目标。沿用已明确的持续执行偏好，不增加设计审批轮次。范围为一个 CLI、一个 Agent、Local SQLite，以及有限 Markdown/TXT 读写；不是独立开发者采用验收。

## 选择与范围

采用独立可安装示例 `examples/local_documents/`，依赖已冻结 SDK `0.1.0a8+maintenance.0608576182db502f`。应用源码、配置、资料、SQLite 与报告均在本地。显式配置的 Chat Completions 模型 API 接收问题、必要的历史和有界资料摘录；配置默认不触发请求。

复用 FileSystemWorkspace 读取、FileSystemWritableWorkspace 新建报告，以及 Runtime / AgentSession / ToolRegistry 的唯一执行权威。另造执行日志、自己重试写入，或引入服务端/向量服务均不符合首版要求。CLI 同时提供交互聊天和独立进程管理命令，使审批暂停与重启恢复可直接演示。

实现选择由维护者承担：有界词法搜索，资料根与输出/状态根分离，报告仅 create-only，不覆盖旧文件。根目录、工具、配置和模型身份固定；修改配置使用新状态目录，旧任务保留原环境。没有任何新 SDK 端口或适配器。

## 应用组成

- `config.py`：严格 TOML 配置、路径和限额、显式环境变量名；不接受内联密钥。配置固定记录不包含凭据值。
- `documents.py`：经原 Workspace 读取 UTF-8 md/txt，有界递归/文件大小/摘录；输出真实相对路径、行号、内容 SHA 与引用 ID。
- `evidence.py`：只读原 SQLite Run/工具结果，核对回答或报告引用确实来自已完成的读取动作；来源表示读取时快照，不冒充当前文件内容。
- `runtime.py`：三个工具 `search_documents`、`read_document`、`save_report`，单 Agent + Session 装配；使用原效果键和原生写回执。写入正文由模型正文加已核验来源组成；审批展示与实际写入使用同一确定性渲染。
- `report_completion.py`：复用原 CompletionVerifier，纯检查报告的已提交保存回执；模型只回答文字时反馈继续，资料不足时拒绝报告完成。
- `cli.py`：chat / ask / report / status / history / approve / resume / cancel。原 Run ID 即恢复入口；重复命令不创建第二效果。
- README、配置样例、演示资料及离线/实际模型验证记录。

## 行为契约

查询的最终 JSON 包含 `answer`、`grounded` 与 `citations`。引用 ID 必须出现在该 Run 已接受的读取结果中；声称有依据却无有效引用时明确报来源错误。未找到资料可以返回不足，不制造引用。这是来源真实性检查，不是任意回答内容的语义正确性保证。

报告请求包含用户指定的 `.md` 文件名。`save_report` 参数包含路径、正文与引用；应用核对与原输入一致、引用有效，追加确定性的来源区。它声明 `idempotent_write`、`requires_approval=True`，真正写入只调用原 Workspace create-only 端口，核验用原 effect key 查询并验证原请求。报告完成后独立读取输出 SHA。拒绝/取消不写目标文件，原 pending 参数不在恢复时重新生成。

报告的成功终态必须有原保存工具的已提交回执。模型提前给出有依据的文字但没有提案时，纯 CompletionVerifier 通过原决策预算内的反馈要求继续；没有依据时明确拒绝报告完成，不通过循环补造证据。它不派发工具、不提交运行状态，也不增加执行权威。

状态查询和 history 不要求密钥，不派发模型。approve 展示完整原正文和绝对目标路径；只有明确确认才提交原 action/digest 决定。批准后可在另一进程 resume；默认普通命令停在 waiting_approval，不自动批准。busy Session 提示原 Run，不能以新 Turn 绕过。

会话由 SDK SQLite 持久化并串行协调。新进程保留同一配置、根目录、数据库和代码；读取历史、重复提交与原 Run 恢复分别可用。等待超时仅结束观察；CLI Ctrl-C 需要显式 cancel 原 Run，在原事件循环观察停止后关闭。正常退出 drain 并保留待批责任；先排空 Runtime 的实际处理器，再关闭注入的文件资源。关闭失败保留原实例供重试。

## 验收

先以真实 SQLite/文件系统和可控 Provider 测试来源、报告拒绝/批准、重复效果、恢复、会话、故障和取消。随后新空目录安装准确 SDK wheel 与独立示例 wheel；实际 DeepSeek 问答、无资料回答、报告预览/批准/跨进程恢复/重复回执及连续会话逐项记录。真实结果与离线 fixture 分开，保留所有失败。SDK 产品未变则不重建或重复全量框架矩阵。

首版门槛全通过后冻结应用版本及 SHA，仅本地提交，保留原 SDK 包/证据；不推送、CI、部署或公开发布。额外模型、平台、RAG、Team、GUI 与生命周期治理都后置。
