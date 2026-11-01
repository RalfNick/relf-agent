# Callable、审批呈现与交付一致性验收（2026-11-01）

基线e94c57c，准确实现提交 `80de9bdc2188d27067c7acd752f5f5a796cbea48`。保留Harness提案、Local／Temporal唯一权威、原Action／审批／效果／预算和资源所有权。本批仅本地提交，单条命令跳过钩子，持久配置不变；不推送、远端CI、部署或公开发行。此前e94c57c的main推送与0CI观察属于已完成的历史事实。

## 准确候选与门槛

SDK `0.1.0a8+maintenance.a97223496646bac0`，wheel SHA `5cfbfec568a26445efd8a9c6009adc60660f320fcf875a747ddfea37e370363b`，sdist SHA `b88d0b054b721f6f8e3eadbf57dcf7c20ddd47ee0e651aaf639299dc80d99a92`。应用 `0.1.0+local.3d98685c70e5` 固定依赖该SDK，wheel SHA `e7a8d3488590ef92d96d96e7e440b763dae099e08d22072b177069b50add4fbf`，sdist SHA `10f48dc1394136be272e7eefe17f72fafcbc22690e2be721c205ce1656c55bb7`。451个SDK产品只有tools.py相对前包改变，原工具持久Manifest／implementation_digest函数AST不变。私有版本只在准确git archive副本同时修改元数据／模块字段，原制品不重建。路径与安装见[当前交付](../../docs/current-delivery.md)和[应用交付](../../docs/local-documents-assistant.md)。

源码／准确安装各 **1407passed**，零失败／错误／跳过，同一ID；原1320与1项deselect保持。分别306.35／304.87秒，独立进程／临时数据库，原期限不变。不是全SDK／平台矩阵。独立运行环境24命令通过，无pytest／Temporal；sdk sdist应用构建安装、两次聊天关闭和前SDK↔新SDK所选默认业务审批／重启／重复回执通过，每例一次效果、零模型请求。没有修改历史业务数据库。

## 五项问题与反例

1. 描述符Callable不再误判。标准property getter按静态MRO／描述符固定，注册／检查不调用getter；普通函数／方法、partial／子类、标准staticmethod／classmethod保持支持。初始正确性RED30失败／13控制通过；最终新增59个例覆盖handler／reconciler／构造／继承／getter纯性等。
2. 类工具构造器固定实际metaclass-call/new/init继承入口，代码或绑定变化在派发／采纳拒绝。自定义不透明描述符、partial.func遮蔽和原身份缺失的独立method-wrapper提前清楚拒绝；不扩展此前不能注册的原生形式。原身份编码保持，动态getter返回的任意辅助callable、状态／参数／默认值／闭包／外部依赖由集成方显式版本化。
3. 人工预览安全呈现。25个终端反例先失败，另有补充格式字符／明确预览说明RED；28项覆盖stdout／stderr／参数错误、ESC／OSC／C0／C1／回车退格／bidi格式和原文保存。中文／换行／tab保持，JSON字段值、原报告字节、SHA、Action／摘要和原生回执不变；真实本地Application跨重开批准／恢复／create-only验证通过，没有真实模型。
4. 当前状态分开记录e94已推送与本次未推送，包公开状态／CI／官网部署分开。原历史JSON与验收不改写。
5. 官网新增仅精确current-delivery路径的main别名，其余repo链接与全部教程代码继续固定300c62c。31项Node测试、14双语对、Astro零错误／警告、本地32页／1985链接资源和固定SDK离线教程通过。构建源检查改为读声明Git快照，保留所有源哈希；本地完整历史预条件／缺失对象明确失败，没有网络fallback或远端校验。

## 审查、原失败与决定

一次fresh集中审查：0Critical／1Important／0Minor。已捕获BuiltinFunction不应重新按owner类名查找；4个RED后直接保留原捕获绑定，相关240项GREEN；只进行这一轮修正，无第二次审查。集成171passed44.76秒先通过，最终门槛以上述精确候选矩阵为准，各集合重叠不累加。

所有原失败／环境失败及修正保留在dist/callable-preview-fixes-20261101。初始Callable测试导入失败和失败GREEN、getter纯性旧测试假设、Node22.9不支持Astro／TS、默认Python不支持tarfilter及缺少CLI脚本均保留。官网最终使用已安装Node25.6.1／Python3.12，离线教程入口shim来自固定基线元数据；不是新模型／平台或部署成绩。

决定沿用当前checkout新codex分支，原未跟踪审查文件保持；并行独立实现、一次集中审查、精确安装合并验收。不扩大opaque原生形式；静态getter返回的动态依赖不递归证明。固定官网源用Git300c62c而非当前工作树，缺失快照明确失败，工作流本来使用完整checkout，无新增远端权限。源码／安装矩阵进程隔离，节点固定且期限不变；失败必须保留后定位，不能以测试数量替代真实外部资格。

## 历史与剩余边界

21份受保护旧制品、前SDK与应用、历史失败和原未跟踪文件SHA保持。代码／包／元数据／源哈希及相对链接由最终审计核对。官网修改仅在本地源码与构建，线上并未更新；main链接仍指公开main，不宣称能访问本地未推送候选。原真实模型成绩保留原包，当前新候选没有模型请求。

已知未闭合斜杠命令引号退出当前聊天的小项继续保留。其他解释器／平台、未选Temporal真实故障窗口、独立采用、公开包安装、完整M1／R01–R26与对等比较继续待验证；所选Local双向恢复不承诺任意旧应用任务自动迁移。机器摘要见[本批结果](../../evals/results/relf-callable-preview-fixes-20261101.json)。
