# 本地资料助手维护候选交付

更新：2026-11-01。本页定义资料助手维护候选的精确制品与验收范围；配套 SDK 同时纳入本批工具入口修复，准确清单见[当前交付](current-delivery.md)。程序、会话、执行记录、资料与报告在本地，显式模型 API 会接收问题、必要历史和选中的资料摘录。

| 项目 | 固定值 |
| --- | --- |
| 应用版本 | `0.1.0+local.ddcf607b0929` |
| 应用源码提交 | `886c64847ccb6baa1e3a3a1b114ba790cdc31aa0` |
| 应用 wheel | `dist/stability-fixes-20261101/application-artifacts/relf_local_documents_example-0.1.0+local.ddcf607b0929-py3-none-any.whl` |
| wheel SHA256 | `04cf1af63f89cbade831e37e556bd560e916116095874d30d5464ab5018a6259` |
| 应用源码包 | `dist/stability-fixes-20261101/application-artifacts/relf_local_documents_example-0.1.0+local.ddcf607b0929.tar.gz`，包含配置样例、演示资料、README、许可证与程序 |
| sdist SHA256 | `f50e2d413e06ad6f05a7d740a1f7450e05aaba9d36f694536ccdf780240b9d31` |
| SDK 依赖 | `0.1.0a8+maintenance.f3da3f48e894e745`；本批修复通用工具直接入口检查 |
| SDK wheel SHA256 | `e742393cf5570ae12e9fe49002b6dd8a0d5ba84eca7d324e2cbfeb0749db9a82` |
| 环境范围 | macOS 15.6.1 ARM64／Python 3.12.7；不自动取得其他平台或模型资格 |

## 从空目录启动精确制品

收到这三份文件后，将下列路径替换为实际绝对路径。不要用索引上同名的 SDK 或源码重建包替代。

```sh
SDK_WHEEL="/ABS/relf_agent-0.1.0a8+maintenance.f3da3f48e894e745-py3-none-any.whl"
APP_WHEEL="/ABS/relf_local_documents_example-0.1.0+local.ddcf607b0929-py3-none-any.whl"
APP_SDIST="/ABS/relf_local_documents_example-0.1.0+local.ddcf607b0929.tar.gz"
mkdir my-local-documents
cd my-local-documents
python3.12 -m venv .venv
. .venv/bin/activate
python - "$SDK_WHEEL" "$APP_WHEEL" "$APP_SDIST" <<'PY_CHECK'
import hashlib
import sys
from pathlib import Path
expected = {'relf_agent-0.1.0a8+maintenance.f3da3f48e894e745-py3-none-any.whl': 'e742393cf5570ae12e9fe49002b6dd8a0d5ba84eca7d324e2cbfeb0749db9a82', 'relf_local_documents_example-0.1.0+local.ddcf607b0929-py3-none-any.whl': '04cf1af63f89cbade831e37e556bd560e916116095874d30d5464ab5018a6259', 'relf_local_documents_example-0.1.0+local.ddcf607b0929.tar.gz': 'f50e2d413e06ad6f05a7d740a1f7450e05aaba9d36f694536ccdf780240b9d31'}
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

源码／准确 SDK＋应用安装各 **1320 项**相同回归通过（其中51项应用测试），零失败／错误／跳过。另有源分发构建反例1项转绿，准确 SDK sdist 中的完整应用在独立环境重新构建／安装成功。仅运行依赖环境没有 pytest／Temporal，双次聊天退出和所选 SDK 旧新双向审批／恢复／去重通过；没有真实模型请求。

长行完整扫描与字符列来源、多行管道／半行取消／UTF-8、工具入口／partial 子类漂移等本批反例均先失败再通过。准确制品与证据见[本批验收](../architecture/reviews/2026-11-01-stability-review-fixes.md)。原首版固定演示资料的12次实际 DeepSeek 调用仍只属于原 `0.1.0+local.52ddc2d194b8`／`.0608576182db502f` 组合，见[原始验收](../architecture/reviews/2026-11-01-local-documents-assistant.md)，本批不把它写成新候选已重新取得的质量成绩。

## 冻结范围与限制

首版是命令行、一个 Agent、Local SQLite 与有限 Markdown/TXT 工具；不引入新 SDK 抽象或分布式能力。来源 ID 证明实际读取的文件快照，不证明任意答案每句话的语义正确性。词法检索与固定限额、未知结果和取消规则见 README。

已知小项：斜杠命令出现未闭合引号会退出本次 CLI 并显示通用输入／I/O 错误；修正后可用原配置重启继续，已有任务与会话不删除。此项保留后续，不继续扩展首版。

独立开发者采用、其他模型／平台、多模态、通用节点与 R01–R26 仍是后续事项。上述维护源码已随 `e94c57c` 合入并推送到 main，所选提交 CI 核对为 0；私有候选文件没有上传或公开发行。当前 Callable／审批预览修复仅本地提交，不推送或部署。文档收尾不改变上述候选文件；原首版应用与 SDK 制品保持原 SHA。旧任务仍须用其原版本、配置和目录恢复，不声明旧应用任务的自动升级。
