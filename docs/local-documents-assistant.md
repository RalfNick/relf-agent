# 本地资料助手首版交付

更新：2026-11-01。本页只定义本地资料助手示例的精确制品与验收范围；框架本身仍沿用[原冻结候选](current-delivery.md)。程序、会话、执行记录、资料与报告在本地，显式模型 API 会接收问题、必要历史和选中的资料摘录。

| 项目 | 固定值 |
| --- | --- |
| 应用版本 | `0.1.0+local.52ddc2d194b8` |
| 应用源码提交 | `1cd0c3cedf6323d505ac14be846232e88a6a1648` |
| 应用 wheel | `dist/local-documents-20261101/artifacts-final/relf_local_documents_example-0.1.0+local.52ddc2d194b8-py3-none-any.whl` |
| wheel SHA256 | `8f8ac49190f0afd0d110d68a3afbe58d7a107f68ae482ce0a87b2cc04935d498` |
| 应用源码包 | `dist/local-documents-20261101/artifacts-final/relf_local_documents_example-0.1.0+local.52ddc2d194b8.tar.gz`，包含配置样例、演示资料、README、许可证与程序 |
| sdist SHA256 | `484a17cbc0b17d02f4387995903aabcfa5be5a4108aae0a1a9e48ba29a90673e` |
| SDK 依赖 | `0.1.0a8+maintenance.0608576182db502f`；未修改或重建 |
| SDK wheel SHA256 | `082b5ec9d1c107539b925d8a9f1332560eb7f92ec518b0e603ad02b5046cb482` |
| 环境范围 | macOS 15.6.1 ARM64／Python 3.12.7；不自动取得其他平台或模型资格 |

## 从空目录启动精确制品

收到这三份文件后，将下列路径替换为实际绝对路径。不要用索引上同名的 SDK 或源码重建包替代。

```sh
SDK_WHEEL="/ABS/relf_agent-0.1.0a8+maintenance.0608576182db502f-py3-none-any.whl"
APP_WHEEL="/ABS/relf_local_documents_example-0.1.0+local.52ddc2d194b8-py3-none-any.whl"
APP_SDIST="/ABS/relf_local_documents_example-0.1.0+local.52ddc2d194b8.tar.gz"
mkdir my-local-documents
cd my-local-documents
python3.12 -m venv .venv
. .venv/bin/activate
python - "$SDK_WHEEL" "$APP_WHEEL" "$APP_SDIST" <<'PY_CHECK'
import hashlib
import sys
from pathlib import Path
expected = {'relf_agent-0.1.0a8+maintenance.0608576182db502f-py3-none-any.whl': '082b5ec9d1c107539b925d8a9f1332560eb7f92ec518b0e603ad02b5046cb482', 'relf_local_documents_example-0.1.0+local.52ddc2d194b8-py3-none-any.whl': '8f8ac49190f0afd0d110d68a3afbe58d7a107f68ae482ce0a87b2cc04935d498', 'relf_local_documents_example-0.1.0+local.52ddc2d194b8.tar.gz': '484a17cbc0b17d02f4387995903aabcfa5be5a4108aae0a1a9e48ba29a90673e'}
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

- 最终源码：完整示例与直接依赖的 Runtime／Session／Workspace／CompletionVerifier 合约 **192 passed**，警告即错误，无跳过。
- 准确 wheel 在仓库外安装：全部 **38 项示例测试通过**，没有 checkout imports；默认 SDK 不依赖 Temporal。
- 另建仅运行依赖的空环境：不安装 pytest 或 Temporal，使用源码包中的配置和演示资料，连续启动／退出两次通过；没有生成请求、任务或报告。
- 实际 DeepSeek：**12 次调用、14 条独立进程命令、35.60 秒**。核对了文件行号／SHA、有依据问答、资料不足拒答、重启会话、审批前零报告、批准后新进程执行、正文与预览一致、重复批准／提交／恢复不增加写入、拒绝后零写入，以及无密钥只读查询。
- 本批选定的报告只有一次工具写尝试；报告 SHA256 为 `623a9df617855da79ea06cd8ab2c62f96dd2accce0c82d2c05af68bf169813ab`。这是所选本地业务证据，不是任意外部操作恰好一次的保证。
- 最终只读审查发现的两项 Important 已用反例修复；原失败、前两份示例候选及 SDK 历史制品保留。细节见[验收记录](../architecture/reviews/2026-11-01-local-documents-assistant.md)。

## 冻结范围与限制

首版是命令行、一个 Agent、Local SQLite 与有限 Markdown/TXT 工具；不引入新 SDK 抽象或分布式能力。来源 ID 证明实际读取的文件快照，不证明任意答案每句话的语义正确性。词法检索与固定限额、未知结果和取消规则见 README。

已知小项：斜杠命令出现未闭合引号会退出本次 CLI 并显示通用输入／I/O 错误；修正后可用原配置重启继续，已有任务与会话不删除。此项保留后续，不继续扩展首版。

独立开发者采用、其他模型／平台、多模态、通用节点与 R01–R26 仍是后续事项。仅本地提交，没有推送、远端 CI、部署或公开发布。文档收尾不改变上述 wheel 或重建原 SDK。
