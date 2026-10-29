# 当前安装包的默认任务验收

本页复现 Local 四条有限参考链路：八类工单、八类知识问答、五类 Plan 和相同五类 Team 库存任务。使用现有 SDK 评测器与独立 oracle；工具脚本仅组合、计量和核对结果，不增加执行权威、后端或模型适配器。

本轮固定的私有 SDK 为 `0.1.0a8+maintenance.54f45574ad74b3af`，wheel SHA256 为 `3ca80c594b9d5e18946f4c016c41655754baee6284c8b96d05bc1107b9f64463`。沿用[上一批唯一制品](../architecture/reviews/2026-10-29-model-free-local-tools.md)，451产品文件不改、不重建。原 a8 不包含此前维护增量；不能用普通 `pip install relf-agent` 代替本次精确安装。

## 准备隔离环境

安装上述精确 wheel，按[语义参考应用](phase1-semantic-rag.md#安装与显式模型下载)准备固定 MiniLM revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` 的11份 safetensors／tokenizer／配置文件。本轮依赖为 sentence-transformers5.7.0、transformers5.19.0、torch2.14.1、huggingface-hub1.33.0，实际环境为 macOS15.6.1 ARM64／Python3.12.7；完整依赖指纹另行保存。其他平台与依赖组合须独立验收。

脚本位于源码的 `tools/evaluate_default_chains.py`，可直接用已安装 SDK 的 Python 执行；不需要把 src 放入 PYTHONPATH。它在派发前逐项核对 wheel／安装字节、模型资产和已安装版本，记录完整冻结输入；不会自动下载模型或寻找凭据。

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/path/to/venv/bin/python /path/to/checkout/tools/evaluate_default_chains.py \
  --offline --wheel /absolute/path/to/the-exact-wheel.whl \
  --model-directory /absolute/path/to/paraphrase-multilingual-MiniLM-L12-v2 \
  --output /absolute/path/to/a-new-offline-directory
```

离线仍使用真实神经 Embedding，但生成由明确 fixture 完成；78行全通过才返回0，`quality_accepted` 仍为 false，model_quality／semantic_quality 保持 null。不能把离线结果算作模型成绩。

## 一次固定真实评测

先在宿主安全配置 `DEEPSEEK_API_KEY`，或使用显式 `--prompt-key` 在终端无回显输入。不要把密钥放入命令参数、数据集、报告或提交。没有凭据时不会隐式寻找其他配置或回退离线。

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/path/to/venv/bin/python /path/to/checkout/tools/evaluate_default_chains.py \
  --live --key-env DEEPSEEK_API_KEY --stream-probe \
  --wheel /absolute/path/to/the-exact-wheel.whl \
  --model-directory /absolute/path/to/paraphrase-multilingual-MiniLM-L12-v2 \
  --output /absolute/path/to/a-new-live-directory
```

`--live` 明确授权收费模型请求。脚本限定 deepseek-flash／非思考／温度0／2048输出token／整次适配调用45秒；每条链路最多96次生成调用，原生流探针另加最多一次。该上限是调用与输出额度，费用未知时保留 null，不承诺硬货币上限。供应商可以更新远端模型权重；冻结的是请求配置和本次证据。

| 链路 | 固定配置与真实评分 |
| --- | --- |
| 单 Agent | JSON mode；准确 apply_fix 回执完成验证；诊断、参数、停止、审批、去重与恢复 |
| 语义 RAG | JSON mode／typed_answers；384D本地神经向量、原摄取与Hybrid、实际可见来源、严格引用／答案与零新增调用重连 |
| Plan | 关闭JSON mode；原规则DAG／researcher与writer；成员验证、父级完成gate、库存和算术回执 |
| Team | 相同库存任务与gate；固定Supervisor，核对真实子Run与当前修订证据 |

全部原案例每个重复3次；总体至少90%、每个案例至少80%，因此三次样本中每案例必须3次均通过。缺失、未尝试、重复行、错误调用量、配置漂移、引用／保护／恢复失败都不能被总体通过率掩盖。JSON mode=False 采用 SDK 原有省略值，不改写 Provider identity；布尔值不能用数字代替。

## 产物与读法

新目录独占创建，包含 inputs.json、四份原始报告、四份测量与私有 SQLite 证据、汇总 summary.json。报告文件0600，目录0700；路径已存在时拒绝覆盖。中断后保留原目录，不自动续跑未知请求、改分母或重试失败行。新的试验必须新建目录并独立记录。

只有四条链路的严格任务检查与物理请求计量均通过，`quality_accepted` 才为 true。原报告包含每案例、每次重复、已知 token usage／未知费用、原回执重放和恢复；公开汇总不包含提示、答案、引用正文或凭据。模型／工具／数据注入、审批与未知效果的原契约不变，见[连续上手](support-journey.md)与[任务评测](task-evaluation.md)。

测量中的 inputs_verified 表示 SDK／模型资产／配置和可选库就绪，权重在原 RAG 应用内加载。任务时延包括原执行与恢复，CPU和进程峰值另列；RSS是累计进程高水位，不能当成每条链路的独立增量内存。同步控制计数来自原 LocalEngine 方法体，含内部调用，不包含异步 drive 或远端运输 Query。

默认质量配置使用 complete；JSON mode 不提供增量文本，因此首段字段为 null。`--stream-probe` 另测一次纯原生 Provider 的首段和完整响应，45秒整次上限，关闭原迭代器；它不执行框架 Run、不进入78行分数，也不是端到端 Agent 首段。

原真实批次计数启用了全帧 Python profiler，其性能数据包含观察器开销，不能代表默认耗时。后续已用同包、同任务分离：原观察器／修复局部观察器／关闭观察的三次中位耗时为7.022／1.781／1.768秒，物理任务和原控制计数相同。修复仅影响评测工具，不回填旧成绩，也不宣称SDK或模型提速，见[观察成本验收](../architecture/reviews/2026-10-29-observer-cost.md)。

当前工具在Python3.12+只监听六个原同步控制方法的局部PY_START，限所有者线程，不读帧参数／正文；已有profiler或监控注册会拒绝启动，不接管外部注册。较早Python使用identity查询的全帧回退，仍有计量成本，本轮未重新授予其他Python平台资格。异常退出也清理原注册；清理失败保留所有权并需重试，不能认为槽位已释放。RSS仍是进程累计高水位。

同包另以离线流式夹具测得就绪0.0535秒、框架首段0.1900秒、完整结果与owned关闭0.1967秒；这只验证端到端边界，不是供应商或业务性能。它与默认complete的首段null、原真实Provider独立探针分别保留。

当前结果与独立数据库／冷重连核对见[验收记录](../architecture/reviews/2026-10-29-default-task-quality.md)及[机器可读汇总](../evals/results/relf-default-quality-20261029.json)。这些有限英文参考任务不证明任意自主规划、中文或大规模业务语料质量、外部采用、完整M1、企业生产或跨框架优势；本轮没有进行AgentScope／LangGraph对等试验。
