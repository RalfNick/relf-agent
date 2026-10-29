# Alpha 8 验证清单

当前独立候选`relf-agent==0.1.0a8`，导入`relf_agent`、CLI`relf`／`relf-*`。基线`ac92006`，包含`7e9fac1`和`ac92006`的扩展失败清理与关闭重试，不新增功能。范围见[a8说明](releases/0.1.0a8.md)，实际证据见[准备记录](../architecture/reviews/2026-10-26-alpha8-candidate.md)。原a7及私有维护包的成绩不授予a8。

## 当前准备状态（2026-10-26）

| 项目 | 当前事实 |
| --- | --- |
| 版本与入口 | a8独立版本；发行名／导入／CLI保持 |
| 固定门禁 | 原311基础＋16恢复＋9中断；追加21所有权＋13CLI清理，共370项及两starter |
| 原包 | 两份a8原包独立冻结；准确SHA与输入树见下表，原a7不重建 |
| 本地安装 | Mac原wheel固定370项／两starter全通过；sdist重建安装574通过／3个可选PyYAML收集跳过、两starter通过；源码598通过 |
| Linux ARM64 | 本轮未执行，不借原a7或私有维护包结果 |
| 原生AMD64／远端CI | 本轮未执行；需推送与手动门禁授权 |
| 账号与公开交付 | 未配置Publisher、未上传、无a8公开Tag／Release，`publication_ready=false` |
| 原制品与官网 | 原a7完整交付／记录保持，官网固定a6，不随a8准备自动更新 |

后续必须在同一准确提交和同两包上完成所选平台报告，再配置账号／Publisher，经授权后上传和公开安装。手动流程及操作边界见[发布流程](releasing.md)、[固定门禁](release-gate.md)和[PyPI准备](pypi-publishing.md)。本轮只本地提交，单次跳过钩子，不推送或公开发布。


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

## 后续源码状态（2026-10-29）

上述准备快照中的“未推送”仅描述2026-10-26的准备范围。其后`199334d`已按用户授权使用RalfNick推送到`main`，保留`[skip ci]`；这没有授予手动远端门禁、账号配置或公开发布资格。

后续[CLI命令退出清理维护](../architecture/reviews/2026-10-29-cli-execution-cleanup.md)属于未纳入原包的源码补丁，仅以私有本地版本验证；上表两份a8原包、manifest及既有成绩不变。Linux ARM64／原生AMD64、远端固定门禁、Publisher及公开安装仍需对准确原包独立验收；本轮不触发这些外部操作。
