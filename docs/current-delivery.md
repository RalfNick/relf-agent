# 当前本地交付

更新：2026-11-01。本页是当前推荐 SDK 与资料助手候选的唯一入口。此前四项 P2／源码包修复的源码 `e94c57c` 已使用 RalfNick 合入并推送到 main，所选提交 CI 核对为 0；安装包仍是私有冻结制品，没有创建 Release。下方保留该候选的验收范围；当前 Callable／审批预览／交付链接修复按授权仅本地验证和提交，不推送、远端 CI、部署或公开发布。

## 当前候选与来源

| 项目 | 当前固定值 |
| --- | --- |
| 实现提交 | `886c64847ccb6baa1e3a3a1b114ba790cdc31aa0` |
| 推荐 SDK | `0.1.0a8+maintenance.f3da3f48e894e745`；发行名 `relf-agent`，导入 `relf_agent`，CLI `relf` |
| SDK wheel | `dist/stability-fixes-20261101/sdk-artifacts/relf_agent-0.1.0a8+maintenance.f3da3f48e894e745-py3-none-any.whl` |
| SDK wheel SHA256 | `e742393cf5570ae12e9fe49002b6dd8a0d5ba84eca7d324e2cbfeb0749db9a82` |
| SDK sdist | `dist/stability-fixes-20261101/sdk-artifacts/relf_agent-0.1.0a8+maintenance.f3da3f48e894e745.tar.gz` |
| SDK sdist SHA256 | `a3f84bbff411181f10cb90b5bed39d345ff0fc63c4de354d3fa7535e6bafc4ea` |
| 推荐资料助手 | `0.1.0+local.ddcf607b0929`；模块 `local_documents`，CLI `relf-docs`，固定依赖上述 SDK |
| 应用 wheel SHA256 | `04cf1af63f89cbade831e37e556bd560e916116095874d30d5464ab5018a6259` |
| 应用 sdist SHA256 | `f50e2d413e06ad6f05a7d740a1f7450e05aaba9d36f694536ccdf780240b9d31` |

SDK 451 产品文件中只有 `tools.py`／`executors.py` 改变。源码基版本仍分别为0.1.0a8／0.1.0；隔离构建同时设置准确发行／模块版本。wheel 与 sdist 是不同文件，各自按上述 SHA 固定。制品内文档保留构建提交的快照，最终验收状态以本页及[本批记录](../architecture/reviews/2026-11-01-stability-review-fixes.md)为准，不用历史文档快照替换当前推荐制品。

## 安装与依赖

将 SDK wheel 的绝对路径替换为本机收到的实际文件，先核对本页 SHA256，再在新目录执行：

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install /ABS/relf_agent-0.1.0a8+maintenance.f3da3f48e894e745-py3-none-any.whl
python -m pip check
relf --version
relf init my-agent
```

资料助手的三份准确材料、完整哈希检查和启动命令见[资料助手交付](local-documents-assistant.md)。默认 SDK 只需原 httpx／jsonschema 依赖，不需要 Temporal、Redis、Docker 或模型密钥；实际模型由使用者显式配置。当前示例按命令行、单 Agent、Local SQLite 与有限 UTF-8 Markdown／TXT 文件范围验收。

## 冻结支持范围

| 范围 | 本批结论 |
| --- | --- |
| 通用工具 | 普通／异步函数、绑定方法、partial（含子类）及 callable 的 handler／reconciler 直接入口固定；派发和结果采纳复核。持久工具 Manifest 不变 |
| Agent／Session／Workflow | 沿用原 Local 组合、审批／预算／效果核验／持久 Session；未增加节点或执行模式 |
| 资料助手 | 全文有界词法检索、准确行／可选字符列、审批保存、独立进程恢复与重复回执；stdin 多行／半行／UTF-8／取消按本批回归 |
| Temporal | 沿用原 History 权威；本批离线客户端／合约测试不代签真实 Service、新组合或 Worker 升级 |
| 模型／RAG／Plan／Team | 现有协议和组件能力不扩展；原固定参考质量仅按其原制品／配置范围保留，本批无新真实模型调用 |
| 平台与治理 | 本批 macOS ARM64／Python3.12；不追加其他平台、完整企业治理、M1／R01–R26、公开发行或独立采用资格 |

工具状态、partial 参数、默认参数、闭包和外部依赖仍需集成方明确版本／配置。新检查不是不可信 Python 隔离。旧任务继续使用原版本、配置、目录与工厂；已发生的外部效果不会因拒绝采纳而回滚。工具入口漂移使托管执行拒绝时，保留原 Run／资源，恢复原实现后处理原任务并重试原 Runtime 关闭。更多限制见[扩展指南](extending.md)。

## 本批验收

- 源码／准确 SDK＋应用安装：各 **1320 passed**，零失败／错误／跳过，测试 ID 一致；保留原1002节点并覆盖本批工具和应用反例。分别492.42／395.39秒，不是全量 SDK 或平台矩阵。
- 根源码包打包反例先失败再通过；最终准确 SDK sdist 中的独立应用重新构建并在仅运行依赖环境安装成功。
- 默认依赖环境无 pytest／Temporal，CLI版本一致；聊天连续两次启动／退出、所选旧↔新 SDK 的原审批／恢复／重复回执通过，每个业务只有一次效果；没有模型请求。
- 最终集中审查的一项 Important（partial 子类入口）通过4个 RED→GREEN 反例修复；原失败、沙箱监听失败、前候选与17份受保护历史制品均保留。

## 已关闭与待验证

本批维护修复和本地交付已完成，不自动新增开发队列。资料助手本批有51项应用回归，原首版真实 DeepSeek 成绩见[原验收](../architecture/reviews/2026-11-01-local-documents-assistant.md)；新候选未重跑真实模型质量。未闭合引号导致当前聊天退出仍是已披露小项。

独立开发者采用、其他模型／平台、未选 Temporal 故障窗口、完整 M1／R01–R26、对等比较以及远端 CI／公开发行分别待验证或另行授权。工程检查不替代这些证据。

<a id="当前执行目标2026-11-01-本地示例-agent"></a>
<a id="当前执行目标2026-10-30-再审后"></a>

## 历史交付与目标

本地资料助手首版目标已完成；原 `0.1.0+local.52ddc2d194b8` 与旧 SDK `0.1.0a8+maintenance.0608576182db502f` 保持原制品与验收，详见[原资料助手验收](../architecture/reviews/2026-11-01-local-documents-assistant.md)和[原框架候选验收](../architecture/reviews/2026-10-30-public-preflight-fixes.md)。原独立接入目标保留为后续事项，流程见[独立接入](independent-onboarding.md)。历史 Alpha、S2／函数指纹记录按各自原范围保留，不由本批重新签署。
