# 有界执行与检查循环

基线 `085c0f5`。本批补一个常用默认组合：执行已有成员，检查已采纳结果，必要时进入下一轮；达到有限次数仍不满足条件则失败。纯策略复用原 Planner／PlanVerifier 和 Dynamic DAG 修订；Local／Temporal 保持各自唯一执行权威。

## 方案选择

比较了三个方向：模型工具参数增量需要独立端口、展示v2和多协议恢复；HTTP PUT／PATCH可降低接口接入成本；有界循环可直接复用现有修订／子Run身份，承接上一批FanOut，先补迭代修订场景。前两项各自后置，不混入本批。用户已要求自主连续、并行开发，本批具体设计由实施者选择，不重新请求确认。

[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)提供条件控制、状态合并及循环限额；[AgentScope官方main](https://github.com/agentscope-ai/agentscope/blob/main/README.md)提供Agent、团队、工具与上下文等组合。本批只交付迭代流程默认策略，不等同通用循环图／共享reducer，也不做对等质量或性能排名。完整模型／工具增量、复合流、多模态、集成及应用治理仍是差距。

## 公共策略

`BoundedLoopPolicy(worker="worker", *, until=None, max_iterations=3, version="1")` 是原两端口的同一不可变配置实现：

- `async plan(request, caller)` 只提出原DAG；`verify(request)` 只返回原Verification。两者均不调用caller、模型或工具，不做I/O或保存执行状态。
- worker用原成员标识规则；max_iterations为严格整数1..32，version为非空字符串。until为原BranchCondition；None默认 `BranchCondition(ValueRef(path=("done",)), True)`。只接受source=input且required=True的ValueRef，路径最多32段，不接受函数谓词或其他节点来源。比较原canonical JSON，支持原negate，不新增运算符。缺少证据路径明确失败。
- revision严格整数0..max_iterations-1；只接受PlanningRequest。plan的results数必须等于revision，verify必须等于revision+1。每项exact `{id, member, result}`，id为非空UTF-8字符串、最多1024字符、全唯一，member必须等于worker。结果为原执行权威按轮次提供的有序、已采纳结果。
- id是不透明调用身份，不在策略里解析Local／Temporal拼写。轮次和结果顺序由执行权威保证，并在真实执行／恢复测试单独核对；策略不声称证明任意外来history的顺序或真实性。这样第三方执行后端不必仿造内置后端ID。
- plan要求所有历史结果均未满足until，verify要求最后一项之前的结果均未满足，防止在已终止结果后继续追加轮次。条件缺路径不能当作不满足。
- 每轮仅提出固定节点 `iteration`，member=worker，input为原 `InputMap({"task": ValueRef(), "previous": Literal(上一结果或None), "iteration": Literal(revision+1)})`，output=ValueRef("iteration")。首轮也执行一次；这不是先检查原始输入的while循环。
- plan仅检查当前若存在的remaining_steps／max_nodes／remaining_revisions是非负严格整数且至少1；不要求覆盖所有剩余可能轮次，因为可以提前满足。原宿主max_revisions／max_steps／预算／深度可更严格。
- verify的最新结果满足条件时返回 `Verification("succeeded", 原最新结果)`；未满足且达到policy上限时返回 `Verification("failed", {"reason":"loop_iteration_limit", "iterations":轮数, "last_result":原最新结果})`；其余返回 `Verification("replan")`。不得用PlanningConclusion把耗尽包装成成功。Local／Temporal沿原各自失败错误码，不为统一文案改权威。

## 装配和兼容

SDK可把同一policy注入 `planners={"bounded-loop": policy}` 和 `plan_verifiers={"bounded-loop": policy}`，定义显式选择planner与verifier。两个角色的显式工厂均为bounded-loop，配置字段worker／until／max_iterations／version。until的JSON使用原DAG条件形式：value为原ref binding，equals为JSON，negate可省略。未知字段和非法配置在资源创建前拒绝。

同配置工厂各自创建纯实例，无新资源owner；必须保持两端配置及Profile／定义匹配，默认组合不自动安装该policy。混用其他Verifier属于显式定制，不承诺仍有默认循环语义；文档强调只选Planner会被原默认CompleteVerifier在第一轮完成。

不得修改Engine、DAGRuntime、TemporalParentState、默认planners／plan_verifiers字典、DTO、绑定格式或静态环检查。使用原逐修订子身份、父子预算、权限、每次审批、unknown核验、取消与真实处理器停止／关闭。保存的提案、结果和核验事实继续由原Store或History负责恢复。

## 验收

先保存有效缺实现RED，再证明纯策略／配置；Local覆盖至少两轮收敛、首轮提前完成、上限失败、原更严限额、审批跨轮重开、unknown、取消、不同轮稳定身份、重复提交，以及修订交接的真实进程切点（原每子进程10秒）。真实Temporal覆盖多轮收敛及第二轮审批等待时Worker重启、重复命令和History重放；在途物理handler全冷恢复与新真实模型质量不由这两项授予。

提供完整无模型、可替换受管理成员的示例和SDK／JSON／TOML指南。冻结唯一私有wheel／sdist，源码／准确隔离安装同ID、纯运行依赖、sdist产品比对、所选默认元数据兼容及同冻结输入完整离线回归。使用原缓存Temporal，不下载服务／模型；不访问模型凭据。原包、失败、并行网站及其他非本批内容保持。完成后仅本地提交，单次跳过钩子，保留skip ci，不推送或公开发布，不关闭完整M1／R01–R26。
