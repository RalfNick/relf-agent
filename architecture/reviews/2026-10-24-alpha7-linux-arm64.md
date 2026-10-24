# a7 原包 Linux ARM64 追加验收与发布操作说明

日期：2026-10-24。维护基线 `8a5898687d20f8a0b4c6e734bb1d4e68253f3de5`。本轮继续首版收尾：复用原 `0.1.0a7` 两包、固定门禁、缓存镜像及哈希锁定依赖，在本机 Docker 完成尚缺的 Linux ARM64 验证，完善当前复验命令及状态。不扩展功能，不修改 SDK、测试、版本或门禁，不构建 a8，不推送、触发远端 CI、配置账号、部署官网或公开发布。

## 原制品与执行条件

| 原包 | SHA256 |
| --- | --- |
| `relf_agent-0.1.0a7-py3-none-any.whl` | `6f4e11f7e1e421dcf31f6085777338fecdefd34248381bd06c8eae3a9f32ea32` |
| `relf_agent-0.1.0a7.tar.gz` | `c6afdb08c69adcb4fe46c32b65d6c0029d3b1179db178cf32fc24da5df323d5b` |

使用 `tools/release_gate_manifest.alpha7.json`，外置 manifest SHA 为 `41ebadcb3ac263a8b1cded3b0b0edbe9067e2a598caaccecdd9b192d7e0aa7f7`。仍是原311基础／16恢复／9中断节点及两 starter，零跳过、warnings-as-errors、原期限保持。脚本、manifest、依赖锁与工作流没有变更，冻结包不覆盖；manifest 的 `not_qualified` 保留冻结时快照，追加资格由本记录和报告提供，不通过改写包或 manifest 声明通过。

宿主 macOS ARM64，Docker daemon 为 Linux aarch64。仅使用已缓存的三份精确镜像，不拉镜像、不下载依赖；安装与执行均 `network=none`。每次一个容器，2 CPU／2 GiB内存／swap0／256 PID上限。`created.json` 中实际 HostConfig 与报告 cgroup v2 的 `cpu.max`、`memory.max`、`memory.swap.max` 均核对。内存峰值是整个容器的 cgroup `memory.peak`，未测宿主或 CPU使用峰值；不将CPU限额当使用率。

## 实际结果

| Python | 基础／恢复／中断测试 | starter | 门禁耗时 | 内存峰值 | 自有容器 |
| --- | --- | --- | --- | --- | --- |
| 3.11.17 | 311／16／9，零失败／错误／跳过 | 2，各一次业务写入 | 71.34 秒 | 326.79 MiB | 已移除 |
| 3.12.15 | 311／16／9，零失败／错误／跳过 | 2，各一次业务写入 | 75.18 秒 | 294.57 MiB | 已移除 |
| 3.13.16 | 311／16／9，零失败／错误／跳过 | 2，各一次业务写入 | 76.66 秒 | 296.66 MiB | 已移除 |

三版各自原报告均 `passed_selected_scope`，零失败／错误／跳过／OOM。按容器 State 的 StartedAt／FinishedAt 复核3.11→3.12→3.13串行顺序，前一容器结束后才开始下一版；自有容器退出码均0，按原所有权标记停止／移除。最高内存峰值 **326.79 MiB**，低于2 GiB限制。本轮没有产品或测试失败，不撤销已有失败记录，也不与旧批次拼接结果。

证据目录 `dist/alpha7-linux-arm64-20261024/`：`linux-arm64/matrix-input.json` 固定本次工具／包摘要与平台，三版子目录保存镜像、实际创建／退出信息、原 JUnit、节点清单、安装和 gate report；`matrix.json` 保存通过／清理状态，`acceptance.json` 独立汇总资源和顺序，`SHA256SUMS` 核对证据文件。所选 **713** 个既有文件摘要一致，含完整a6交付、a7原包及构建输入、原架构review、门禁和官网基线；442产品与990测试输入仍与a7冻结输入一致。

## 文档改进及复核

`docs/release-gate.md` 增加当前 a7 的只读 plan、Mac原包、Linux ARM64直接命令，所有示例显式指定a7 manifest；旧a2默认与历史命令保留在历史章节，不自动改默认。三段bash语法与实际只读plan已验证，plan返回a7、311／16／9且不创建文件；真实Linux命令即本轮执行命令，输出使用独立目录。

更新a7清单、发行说明、当前实现摘要、发布页和剩余待办，区分已推送源码、原包本地资格、原生AMD64待验及公开发行。`8a58986` 之前已通过已核验的RalfNick账号推送，GitHub只读回执当次Actions为0、网站构建skipped；这不是远端SDK门禁成绩，也不为本轮增加推送授权。官网继续固定a6的 `ba1c81f`，不修改教程内容、SDK基线或部署；25项网站测试、14对双语来源摘要及49个固定仓库目标检查通过，摘要锁和网站源文件无需变更。

本轮只更改验收文档，不重复运行源码503项或sdist498项，不将其当本轮新成绩；原a7本地安装记录保持其出处。新的Linux实际成绩只验收所选基础SDK，不扩展S2、函数指纹、真实模型、企业部署或R01–R26资格。

## 仍需完成

1. 使用同两包，在原生Linux AMD64宿主以原2 CPU／2 GiB条件串行运行三版Python的固定门禁。远端CI需要另行授权；Mac上的ARM64容器结果不能代签它。
2. 配置 `relf-agent` 在TestPyPI／PyPI的项目权限、`alpha7-pypi-publish.yml` Trusted Publisher和GitHub受保护环境。配置完成不等于上传成功。
3. 获准后仅上传原两包，核对公开摘要、源码外实际安装、两 starter与连续示例，再更新公开推荐与网站基线；不以源码已推送表示a7已公开发行。

历史原制品、失败与未覆盖范围保持。本批文档完成后本地提交，沿用单次跳过钩子及 `[skip ci]`，永久钩子配置不改，不推送。
