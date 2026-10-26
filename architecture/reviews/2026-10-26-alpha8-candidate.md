# Alpha 8 独立候选准备与本地验收

日期：2026-10-26。基线`ac920069e206f39d75ef0ab334f41b0619ca5a27`，纳入该提交及`7e9fac1`的近期维护修复。用户授权准备`0.1.0a8`、统一制品／门禁／文档、完成本地安装并本地提交，单次跳过钩子。不扩功能，不推送、触发远端CI、配置账号、部署官网或公开发布。

## 固定范围与原始记录

沿用`relf-agent`／`relf_agent`／`relf`，原数据与执行协议身份保持。产品相对维护基线只改变`__version__`和生成应用的安装提示，不改变已修复的CLI、Builder、Router、Local／Temporal执行权威、模型或存储契约。原a7完整交付、历史manifest／工作流／发布检查器、各历史review和私有维护验证在开始前记录6806个文件的保护摘要，结束时逐一复核。

新增a8外置manifest、独立发布检查器和仅手动暂存／原生门禁／OIDC发布定义；共享暂存入口只增加a8前缀和完整公共入口校验，历史身份保持。固定门禁保留311基础／16恢复／9中断，追加21所有权／13CLI清理，共370项及两starter；原依赖锁、收集摘要、警告政策、期限和Linux资源限制不降低。

sdist内manifest是构建输入快照，`artifacts={}`；最终两包、输入树和实际验收在外置manifest和交付目录登记。官网继续固定a6源码和教程，不随a8准备更新或部署。

## 最初反例与保留证据

首次新发布测试为**13失败／14通过／32setup错误**：a8元数据、暂存身份、manifest、检查器和工作流尚未准备，原日志与JUnit保留。后续本地实际结果将按同一最终制品追加，不将此前维护源码的14,334通过／891条件跳过、原a7平台或私有维护包成绩重新标为a8。

本批没有真实模型或外部服务调用，不重新执行S2／函数指纹专项，历史专项保持其原输入与资格。Linux／原生AMD64／远端CI、账号、上传和公开安装另行验收。

证据目录`dist/alpha8-candidate/evidence/`，原包目录`dist/alpha8-candidate/`。输入快照和最初失败保留，冻结后在此追加精确SHA、源码／安装结果、完整性和后续待办。

## 源码回归发现的观察夹具问题

首次37模块回归为597通过／1失败：`test_terminal_history_is_not_retained_as_runtime_tasks`在100次调用后立即断言running=0，实际为1。原日志／JUnit保留，不能称为通过。SDK相对ac92006仅版本与安装文字改变。

原ac92006与a8普通100次观察诊断各完成且最终idle；一次确定性真实LocalEngine驱动包装使Run已succeeded、wait返回state_reached，而原宿主驱动仍等待返回，此时running=1，释放并完成后为0。该探针证明终态观察不承诺Task／回调同时完成；它不追认首轮瞬态失败的精确调度顺序。独立只读复核得到相同契约结论，不建议改产品。初次诊断脚本误读`reason`字段导致的AttributeError另行保留，修正为原`wait_reason`后才完成取证，不算产品失败或验收。

只修测试观察：保留每次wait_timeout=1，逐个断言succeeded／ok及离线Provider调用100次；在原任务继续运行的事件循环中，用1秒有界的纯观察等待回调settle，再保留原完整idle断言。不关闭、drain、取消、resume或新建业务任务，不放宽产品／固定门禁期限。随后按同一输入组完整重验，最终结果见下表，不与首轮597项拼接。

冻结后只读复核勘误：sdist构建输入快照中，上段调用计数曾误写为“真实模型调用100次”，正确含义是离线ScriptedProvider调用100次。外置说明已修正，保留原输入快照与固定制品；本批没有调用真实模型，不据该计数授予模型质量资格。


## 本地实际验收（2026-10-26）

| 验证范围 | 本次结果 |
| --- | --- |
| 受影响源码37模块 | **598 passed**，零失败／错误／跳过，warnings-as-errors；不是全量SDK回归 |
| 新a8发布配置与拒绝反例 | **61 passed**，包含实际固定收集；是上行的子集，不重复相加 |
| 原wheel，macOS ARM64／Python3.12.7 | **311基础＋16恢复＋9中断＋21所有权＋13CLI清理**，共370项，零失败／错误／跳过；两starter各一次业务写入 |
| sdist重建后源码SDK目录外安装 | **574 passed／3 skipped**，零失败／错误；仅最小依赖无PyYAML的a6／a7／a8工作流收集跳过，其24项源码检查已通过；两starter各一次业务写入 |
| 制品与入口 | wheel／sdist／维护产品树／重建wheel的442产品文件一致；重建wheel与原wheel SHA完全一致，8CLI、METADATA、LICENSE／NOTICE、pip check、Twine7 strict与离线发布预检通过 |
| 原始记录与官网 | 开始前6806个保护文件逐一核对；原a7及私有维护包、历史manifest／工作流／检查器／review保留；官网固定a6且不部署 |

源码598、安装574、新发布61及固定370之间存在重叠，不累加成唯一测试总数。固定门禁零跳过；安装3个可选工作流模块跳过不属于固定370项。本轮没有全量SDK、Linux、真实模型／服务、S2或函数指纹的新成绩。

### 本地推荐原包

目录`dist/alpha8-candidate/`，只使用以下两份原包，不上传整个dist目录。

| 原包 | SHA256 |
| --- | --- |
| `relf_agent-0.1.0a8-py3-none-any.whl` | `0f88f2d84985e21c340686fe3541020387d4f00ff0cde5613f12a587399e0a45` |
| `relf_agent-0.1.0a8.tar.gz` | `73722d2209b8177b0947a089ab1728daf6b6a3b9715fd38bffa0f8bc76e677ba` |

最终外置manifest SHA256：`597b002cd25f014c96bc1abf4e23a73d1d08ff39ebe7c8bd0ccee8af7a93af26`。构建输入manifest SHA256：`467da6fa96bf372d7ca11236a021df488fbf6761b82b901cfcb9fa232c637d57`；source-inputs.json文件SHA256：`007962c013101f3fbcdd2767925290065bd760d03e59446d3ff8ef13e88e813b`。输入快照含2117源码输入、996测试／示例和442产品文件；来自`ac92006`加本次发布工作区，**不是某个Git提交的逐文件archive**。

归档保留准备时的构建输入说明，最终SHA、结果和文档勘误在外置记录追加以避免自引用；产品和测试不在冻结后修改。原a7及私有维护包不包含或代表此a8原包，不能借用其验收。

### 后续尚未执行

a8的Linux ARM64、原生AMD64／远端固定门禁、账号及Trusted Publisher核对、获准上传与公开安装均未在本轮执行。必须使用以上同两包，Linux保持2CPU／2GiB／swap0／断网、Python3.11–3.13串行；不得用网站CI、原a7或私有维护包报告放行a8。

远端流程为`alpha8-stage-candidate.yml`→`alpha8-release-gate.yml`→`alpha8-pypi-publish.yml`，需要同一不可变提交和准确run／attempt。下一步需先授权推送及手动远端CI；Publisher项目`relf-agent`、仓库`RalfNick/relf-agent`、工作流`alpha8-pypi-publish.yml`与环境`testpypi`／`pypi`仍须维护者核对配置。当前`publication_ready=false`，无a8公开Tag／Release／上传。

## 汇总脚本与独立复核

sdist安装测试原始JUnit已完成574通过／3跳过后，汇总脚本误从skipped的message读取依赖原因（实际message是collection skipped，详情在text），触发AssertionError。原日志及原脚本保留；只修正证据字段读取，复核原JUnit的574个非可选节点与源码一一相同，再执行尚未运行的两starter并生成回执，没有重跑或改写测试。它属于汇总脚本错误，不是SDK失败。

独立只读复核确认发布身份／工作流、原a7保护、实际归档产品／测试／新控制文件及双manifest指向；当前文档a7残留与离线Provider计数措辞已修正，原始勘误快照保留。最终安装和完整性复核结果另据实际证据记录。

## 最终核对

最终只读复核实际两包、重建wheel、双manifest、输入树、安装回执和外置文档后，没有剩余可行动P1／P2／P3。复核未运行测试、构建、Docker或网络操作。Ruff通过，1451文件格式通过，Git空白检查与1012个修改文档／当前仓库目标链接核对通过；原始失败、诊断和汇总脚本错误全部保留。

6806个保护文件摘要一致，442产品和996测试输入在最终冻结后不变；只有外置SHA／成绩／文档勘误、门禁默认选择说明和计划完成状态更新。不重建原a7或已冻结a8，官网不改；本地提交单次跳过钩子、保留`[skip ci]`，永久钩子配置不改，不推送、触发远端CI或公开发布。
