# 当前本地交付

更新：2026-11-01。本页是当前 SDK／资料助手私有候选的唯一入口。此前源码 `e94c57c` 已使用 RalfNick 合入并推送 main，当时两个所选提交 CI 运行数核对为 0；包仍按本地文件交付，没有创建 Release。本次三项 P2／两项 P3 修复的源码与新制品仅本地提交，未推送、触发远端 CI、部署官网或公开发行。

## 当前候选与来源

| 项目 | 当前固定值 |
| --- | --- |
| 实现提交 | `80de9bdc2188d27067c7acd752f5f5a796cbea48`，本地 `codex/callable-preview-fixes` 分支 |
| SDK | `0.1.0a8+maintenance.a97223496646bac0`；发行名 relf-agent，导入 relf_agent，CLI relf |
| SDK wheel | `dist/callable-preview-fixes-20261101/sdk-artifacts/relf_agent-0.1.0a8+maintenance.a97223496646bac0-py3-none-any.whl` |
| SDK wheel SHA256 | `5cfbfec568a26445efd8a9c6009adc60660f320fcf875a747ddfea37e370363b` |
| SDK sdist | `dist/callable-preview-fixes-20261101/sdk-artifacts/relf_agent-0.1.0a8+maintenance.a97223496646bac0.tar.gz` |
| SDK sdist SHA256 | `b88d0b054b721f6f8e3eadbf57dcf7c20ddd47ee0e651aaf639299dc80d99a92` |
| 资料助手 | `0.1.0+local.3d98685c70e5`，精确依赖上述 SDK；模块 local_documents，CLI relf-docs |
| 应用 wheel | `dist/callable-preview-fixes-20261101/application-artifacts/relf_local_documents_example-0.1.0+local.3d98685c70e5-py3-none-any.whl` |
| 应用 wheel SHA256 | `e7a8d3488590ef92d96d96e7e440b763dae099e08d22072b177069b50add4fbf` |
| 应用 sdist | `dist/callable-preview-fixes-20261101/application-artifacts/relf_local_documents_example-0.1.0+local.3d98685c70e5.tar.gz` |
| 应用 sdist SHA256 | `10f48dc1394136be272e7eefe17f72fafcbc22690e2be721c205ce1656c55bb7` |

相对前候选 `.f3da3f48e894e745`，451个SDK产品文件只有tools.py改变；应用只修复人工呈现并固定依赖。源码基版本仍是0.1.0a8／0.1.0，隔离构建副本同时设置发行与模块私有版本。制品内文档是准确构建提交快照，最终验收以本页和[本批记录](../architecture/reviews/2026-11-01-callable-preview-fixes.md)为准；文档收尾不重建已冻结包。

## 安装与依赖

先核对本页SHA，将文件名替换为收到的实际绝对路径，再从新目录执行：

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install /ABS/relf_agent-0.1.0a8+maintenance.a97223496646bac0-py3-none-any.whl
python -m pip check
relf --version
relf init my-agent
```

资料助手的三份准确材料、完整哈希核对与启动步骤见[应用交付](local-documents-assistant.md)。默认SDK仅需原httpx／jsonschema，不需Temporal、Redis、Docker或模型密钥；实际模型由使用者显式配置。没有新增依赖或公共执行接口。

## 冻结支持范围

| 范围 | 本批已验证与边界 |
| --- | --- |
| Callable | 普通函数／方法、partial与子类、Python／标准property的__call__、类的有效metaclass-call/new/init继承入口静态固定；已捕获原生函数保留原绑定，不按类名重取。未知描述符、partial.func遮蔽和无原身份元数据的method-wrapper提前明确拒绝 |
| 身份与恢复 | 原持久工具Manifest／implementation_digest不变；getter返回的任意辅助对象、闭包／默认参数／状态／外部依赖仍需显式version/config；不递归证明任意Python执行图 |
| 审批呈现 | 人工stdout/stderr使终端控制与格式字符可见；预览明确标注转义显示。原始正文、SHA、Action／摘要、JSON字段值和保存回执不变 |
| 原执行链路 | 沿用Agent／Session／Workflow、预算／审批／unknown核验和Local／Temporal各自权威；没有增加后端、节点或执行模式 |
| 官网 | 本地源码的当前交付链接指向main；教程代码／其他repo链接、元数据日期和源哈希仍固定300c62c。仅本地构建，没有部署或线上核验；main链接展示公开main而非本地未推送的新候选 |
| 验收资格 | 本批macOS ARM64／Python3.12；原模型、平台和Service成绩保持原制品范围，不授予新平台、真实模型或企业完整资格 |

具体允许／拒绝形态见[扩展指南](extending.md)。原应用任务仍须保留原代码、配置、数据库和目录恢复；本批不提供自动任务迁移。直接代码变更被拒绝时保留原证据与资源，恢复原实现后处理原Run并重试原实例关闭，已发生的外部效果不会回滚。

## 本批验收

- 源码与准确SDK＋应用安装各 **1407 passed**，零失败／错误／跳过，同一测试ID；原1320节点和1项排除保持，分别306.35／304.87秒。矩阵在独立进程／临时数据库中执行，不是全SDK或平台验收。
- 新增59项Callable与28项终端反例；集中审查的已捕获原生方法误判以4个RED闭环，相关240项转绿。原失败与环境失败保留。
- 独立运行依赖环境无pytest／Temporal，24条命令通过；准确SDK sdist中的应用重新构建／安装成功；聊天双次启动关闭无Run或模型请求；所选前SDK↔新SDK默认业务审批／重启／去重双向通过，每例一次效果。
- 官网31项测试、14对双语源核对、Astro零错误／警告、本地32页构建与1985链接／资源核对通过；固定教程离线命令验证通过。没有远端检查、部署或线上资格。
- 21份历史制品和原始记录保持，原未跟踪审查文件没有修改或代为提交。

## 已关闭与待验证

本批五项问题已收口，不自动增加开发队列。新候选没有真实模型调用或新Service／平台验收。所选真实模型任务质量、其他平台／解释器、其余Temporal故障窗口、独立采用、公开包／索引安装、完整M1／R01–R26和对等比较仍独立待验证。未闭合斜杠命令引号退出当前聊天的已知小项保留。

<a id="当前执行目标2026-11-01-本地示例-agent"></a>
<a id="当前执行目标2026-10-30-再审后"></a>

## 历史交付与目标

资料助手首版及前次四项P2／源码包修复已经完成，原 `.f3da3f48e894e745`／应用 `0.1.0+local.ddcf607b0929` 保持原SHA与[验收](../architecture/reviews/2026-11-01-stability-review-fixes.md)。更早SDK／应用、Alpha、S2和函数指纹记录按原范围保留。独立业务采用继续后续，见[接入流程](independent-onboarding.md)。新源码推送、CI、发布或官网部署均需另外明确授权。
