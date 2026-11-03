# 基础工具与增量配置补齐验收（2026-11-03）

基线 `f0bf274`；用户新授权为“持续优化框架，补充缺失的能力”。本批仅补既有 R04／R12／R22 的两个有限缺口，未改变 Local／Temporal 单一执行权威，没有新增依赖或公开 Alpha。用户随后授权将本批源码、测试与文档本地提交，并仅对该次提交跳过钩子；没有推送、远端 CI、官网部署或公开发行。原推荐 SDK／资料助手候选继续按[当前交付](../../docs/current-delivery.md)保留。

## 已实现

| 能力 | 默认与扩展 | 本批边界 |
| --- | --- | --- |
| 固定 HTTP GET | `HTTPToolSource(method="GET", query_parameters=...)`；原 `tools/http-json` 的 SDK／JSON／TOML 声明共用；可换原 ToolSource | 固定 URL／方法／头；标量／重复参数，显式映射、编码限额与 Schema；GET 不自动决定工具效果；不开放动态 URL、凭据代理或通用请求模板 |
| 增量策略配置 | `components.stream_updates` 选择 `bounded`；原四项 StreamUpdatePolicy 参数；Local sync／async、Temporal async 装配 | 默认仍 None，原 Manifest 不变；工具显式 emit，模型仍需原 SDK wrapper／宿主工厂；不增加 wrapper 清理归属、StreamChannel 或新观察协议 |

5个既有产品文件及1个新增纯工厂改变，共452产品文件；版本号只在独立构建副本加私有标识。HTTP默认POST的持久身份与六位置参数调用保持；新GET的固定映射写入原Source身份。省略新组件的策略与历史发布保持不变。

设计与实施步骤见[设计](../../docs/superpowers/specs/2026-11-03-foundation-gaps-design.md)和[计划](../../docs/superpowers/plans/2026-11-03-foundation-gaps.md)。具体使用见[HTTP工具](../../docs/http-tools.md)和[增量配置](../../docs/agent-stream-updates.md#jsontoml-配置展示策略)。

## 审查与失败记录

独立整批审查确认1项P2：原URL校验容许末尾空`?`／`#`，GET直接拼接会错参／丢参。3个反例实际失败后，改为仅GET构造拒绝裸分隔符；POST原行为和身份不改。最终相关矩阵包含此反例，没有额外P1／P3待处理。

HTTP接口缺失的初始反例31失败／12通过，策略缺失83失败／6通过；累计多参数编码超限另有有效变异反例。组合测试最初因sandbox拒绝本机bind失败，获准使用127.0.0.1后在缺失组件处正确失败。中间的两个终态回执配置假设、非字符串Profile键假设和一次错误测试文件名分别纠正，没有为通过测试改写原产品语义。最小依赖辅助脚本最初误用不存在的`runtime.engine`，已改用公共diagnostics并在全新环境完整重跑。所有失败和最终日志留在`dist/foundation-gaps-20261103/`，没有覆盖原记录。

## 最终验证

| 范围 | 结果 |
| --- | --- |
| 源码相关矩阵 | 440 passed，零失败／错误／跳过；pytest 35.17秒 |
| checkout外准确wheel安装 | 同440个测试ID，全部通过；pytest 37.79秒；模块来自site-packages |
| 安装后组合恢复 | GET审批前关闭、重开批准、重复命令／批准与已完成再开；仅一次请求和一个原tool_end；不虚构GET进度delta |
| 原POST双向兼容 | 原`.a97223496646bac0`→新→原、新→原→新，两条审批恢复均通过；每条一次POST，原回执／事件不重复；使用新临时数据库 |
| 最小运行依赖 | 10条命令通过；无pytest／Temporal，pip check、CLI版本／帮助／starter、配置运行及sdist重建／重装通过 |
| 制品与完整性 | 源码、wheel、sdist及安装452产品逐文件一致（构建副本的版本赋值单列）；sdist重建wheel同452产品；290份原wheel／sdist和用户原未跟踪审查文件SHA不变 |
| 静态检查 | 全src／tests Ruff与格式检查、Git空白检查通过 |

相关矩阵覆盖HTTP／ToolSource／CLI、增量／实际关闭与取消、Local／Temporal配置及装配；不是全SDK回归。独立审查101项是重叠子集，不叠加为总数。机器摘要见[结果](../../evals/results/relf-foundation-gaps-20261103.json)。

本地提交仅固化既有改动、测试及最终文档，不重新构建验证包。制品清单和机器摘要中的 `source_is_uncommitted=true` 描述构建当时的工作区快照；其基线、产品哈希与原验收成绩保持，不能解释为提交之后的实时状态。

## 本地验证制品

版本：`0.1.0a8+foundation.4d5f21d82d5d96bd`，来源是基线加当前工作区产品SHA清单，不冒称某个已提交快照。

- wheel：`dist/foundation-gaps-20261103/sdk-artifacts/relf_agent-0.1.0a8+foundation.4d5f21d82d5d96bd-py3-none-any.whl`；SHA256 `a997c3b5835534b93e4ae3c2b05bd3e2f420de96510be0d24345aa48a57dfc6f`。
- sdist：`dist/foundation-gaps-20261103/sdk-artifacts/relf_agent-0.1.0a8+foundation.4d5f21d82d5d96bd.tar.gz`；SHA256 `10f0bdd0238ab61b1d63fb5565dee5f3fd4ce8378badb51e74617b74ac967a71`。

完整来源／产品哈希清单是`dist/foundation-gaps-20261103/candidate.json`。制品内文档为构建时快照，最终验收以本记录和机器摘要为准；本记录收尾不重建原包，也不将本地验证包替换为推荐发行包。

新目录安装时核对上述哈希，使用实际文件路径：

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install /ABS/relf_agent-0.1.0a8+foundation.4d5f21d82d5d96bd-py3-none-any.whl
python -m pip check
relf --version
relf init my-agent
```

## 仍未验收与后续边界

本批环境为macOS ARM64／Python 3.12.7；仅本机真实HTTP服务和离线Temporal SDK，未调用真实模型／远端业务／真实Temporal Service。新配置的高级组合故障窗口、其他平台／解释器、真实模型流、外部采用和完整R01–R26不借本批成绩验收。原S2、函数指纹、平台与质量记录保留原制品／环境资格。

剩余明显能力仍包括通用受管理异步节点、逐记录流式Workflow、受限循环／合并策略、完整异步Profile路由、Embedding／Vector公共契约套件及更广服务治理；本批没有启动它们。先按具体使用需求选择下一项，保持可替换端口、版本固定及原恢复责任。
