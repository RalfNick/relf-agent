# 本地资料助手维护候选交付

更新：2026-11-01。本页定义资料助手维护候选的精确制品与验收范围；配套 SDK 同时纳入本批 Callable 边界修复，准确清单见[当前交付](current-delivery.md)。程序、会话、执行记录、资料与报告在本地，显式模型 API 会接收问题、必要历史和选中的资料摘录。

| 项目 | 固定值 |
| --- | --- |
| 应用版本 | `0.1.0+local.3d98685c70e5` |
| 应用源码提交 | `80de9bdc2188d27067c7acd752f5f5a796cbea48` |
| 应用 wheel | `dist/callable-preview-fixes-20261101/application-artifacts/relf_local_documents_example-0.1.0+local.3d98685c70e5-py3-none-any.whl` |
| wheel SHA256 | `e7a8d3488590ef92d96d96e7e440b763dae099e08d22072b177069b50add4fbf` |
| 应用源码包 | `dist/callable-preview-fixes-20261101/application-artifacts/relf_local_documents_example-0.1.0+local.3d98685c70e5.tar.gz`，包含配置样例、演示资料、README、许可证与程序 |
| sdist SHA256 | `10f48dc1394136be272e7eefe17f72fafcbc22690e2be721c205ce1656c55bb7` |
| SDK 依赖 | `0.1.0a8+maintenance.a97223496646bac0`；本批修复描述符与构造器入口固定 |
| SDK wheel SHA256 | `5cfbfec568a26445efd8a9c6009adc60660f320fcf875a747ddfea37e370363b` |
| 环境范围 | macOS 15.6.1 ARM64／Python 3.12.7；不自动取得其他平台或模型资格 |

## 从空目录启动精确制品

收到这三份文件后，将下列路径替换为实际绝对路径。不要用索引上同名的 SDK 或源码重建包替代。

```sh
SDK_WHEEL="/ABS/relf_agent-0.1.0a8+maintenance.a97223496646bac0-py3-none-any.whl"
APP_WHEEL="/ABS/relf_local_documents_example-0.1.0+local.3d98685c70e5-py3-none-any.whl"
APP_SDIST="/ABS/relf_local_documents_example-0.1.0+local.3d98685c70e5.tar.gz"
mkdir my-local-documents
cd my-local-documents
python3.12 -m venv .venv
. .venv/bin/activate
python - "$SDK_WHEEL" "$APP_WHEEL" "$APP_SDIST" <<'PY_CHECK'
import hashlib
import sys
from pathlib import Path
expected = {'relf_agent-0.1.0a8+maintenance.a97223496646bac0-py3-none-any.whl': '5cfbfec568a26445efd8a9c6009adc60660f320fcf875a747ddfea37e370363b', 'relf_local_documents_example-0.1.0+local.3d98685c70e5-py3-none-any.whl': 'e7a8d3488590ef92d96d96e7e440b763dae099e08d22072b177069b50add4fbf', 'relf_local_documents_example-0.1.0+local.3d98685c70e5.tar.gz': '10f48dc1394136be272e7eefe17f72fafcbc22690e2be721c205ce1656c55bb7'}
for name in sys.argv[1:]:
    path = Path(name)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[path.name], path.name
print("三份制品 SHA256 一致")
PY_CHECK
python -m pip install "$SDK_WHEEL" "$APP_WHEEL"
python -m pip check
mkdir materials
tar -xzf "$APP_SDIST" -C materials --strip-components=1
cp materials/assistant.example.toml assistant.toml
cp -R materials/demo-documents demo-documents
printf 'Model API key: '
read -r -s DEEPSEEK_API_KEY
printf '\n'
export DEEPSEEK_API_KEY
relf-docs --config assistant.toml chat
```

样例明确配置 `deepseek-flash`／`https://api.deepseek.com`，凭据只用环境变量。可修改样例为自己的明确配置；已接受任务恢复仍须保留原配置、代码、数据库和目录。完整的单条问答、报告提案、独立进程批准／恢复、重复回执、拒绝、取消与历史命令见[示例 README](../examples/local_documents/README.md)。

## 已取得的证据

源码／准确SDK＋应用安装各 **1407项**相同回归通过（其中79项应用测试），零失败／错误／跳过；原1320节点及1项排除保留。59项Callable与28项终端新反例覆盖未变更描述符、类构造器／继承入口、捕获原生方法和安全呈现；原始报告字节、SHA与审批身份保持。

运行依赖空环境无pytest／Temporal，24条安装／聊天／前后SDK审批恢复与去重命令通过；准确SDK源码包内应用可重新构建并安装。本批没有真实模型请求。准确制品与证据见[本批验收](../architecture/reviews/2026-11-01-callable-preview-fixes.md)，原首版实际DeepSeek成绩仍只属于[原包与配置](../architecture/reviews/2026-11-01-local-documents-assistant.md)。

人工输出使ANSI／OSC、回车／退格、C0／C1及Unicode格式控制符显示为可见转义，保留普通中文、换行和制表符；预览注明保存原文，JSON仍保留原字段。显示文字不能替代原正文、SHA或摘要重新提交。

## 冻结范围与限制

首版是命令行、一个 Agent、Local SQLite 与有限 Markdown/TXT 工具；不引入新 SDK 抽象或分布式能力。来源 ID 证明实际读取的文件快照，不证明任意答案每句话的语义正确性。词法检索与固定限额、未知结果和取消规则见 README。

已知小项：斜杠命令出现未闭合引号会退出本次 CLI 并显示通用输入／I/O 错误；修正后可用原配置重启继续，已有任务与会话不删除。此项保留后续，不继续扩展首版。

独立开发者采用、其他模型／平台、多模态、通用节点与 R01–R26 仍是后续事项。此前维护源码 e94c57c 已合入并推送 main，当时CI核对为0；本页所列新候选源码仅本地提交，未推送、部署或公开发行。文档收尾不改变上述候选文件；原首版应用与 SDK 制品保持原 SHA。旧任务仍须用其原版本、配置和目录恢复，不声明旧应用任务的自动升级。
