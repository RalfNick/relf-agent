# 从空目录接入自己的业务

本流程使用[当前交付入口](current-delivery.md)的同一精确候选。目的不是再验收框架全部能力，而是观察未参与框架开发的人能否独立完成模型／工具替换、审批及新进程恢复。当前外部参与者未建立，采用状态为**待验证**；维护者或AI运行同样命令只记为内部演练。

## 参与与记录

复制[记录模板](templates/independent-onboarding-report.md)，参与者先写业务目标、环境、候选完整版本／SHA和是否参与框架开发，开始计时。保留所有失败、求助、修改和命令耗时；不得将框架开发者代写应用的过程计为独立完成。记录中不保存密钥、个人或生产业务数据。

使用一个参与者自己的有限测试业务，例如测试工单处理、库存预留或配置变更；预先写清准确输入、预期工具参数、授权人和独立结果验证方式。测试业务须有幂等键或可靠的效果核验接口。没有这些条件时先记为阻塞，不通过关闭审批或改成只读来假装完成写操作验收。

## 1. 在空目录安装

按[精确安装命令](current-delivery.md#安装与依赖)从空目录建立venv；不editable安装、不设置指向checkout/src的PYTHONPATH。记录文件SHA、`pip check`、元数据／模块／CLI版本以及模块实际路径。此后所有命令均在生成的app目录，不依赖仓库examples。

```bash
python -m agent_app --ticket INC-001
```

先用默认本地业务理解审批；从输出抄录原Run／Action／摘要，使用显示的inspect、approve、resume命令，不手工猜ID。默认写入前应为waiting_approval，业务库没有新写入。这个基线是fixture运行，不是自有业务或真实模型成绩。

## 2. 替换自己的模型和工具

编辑已生成的`agent_app/runtime.py`，只使用已有SDK接口：

- 用自己的显式Provider替换`providers={"default": OfflineProvider()}`里的实例，或按[模型SDK](sdk-model-tools.md)选择原生Provider。异步complete返回原ModelResponse；不要在Provider里直接执行工具。凭据只由宿主环境提供，记录端点／型号／凭据环境变量名，禁止记录值。
- 修改`agent_spec()`的业务指令和输出Schema；替换read_ticket／apply_change／verify_change的业务查询、操作与结果核验。也可重命名工具，但需同时修改Spec、Schema、模型说明和恢复工厂，冻结后不再漂移。
- 写工具保留明确效果类别、requires_approval、稳定业务配置身份。把`context.effect_key`传给真实测试服务；reconcile按同一键查询原结果。不要把本地演示的ChangeService当作任意生产API的幂等保证。
- 执行记录继续用独立SQLite；可以按[替换示例](support-journey.md#继续定制与恢复)替换Session／Facts后端，但这不是本次独立接入的强制扩展任务。异步工具使用现有ToolRegistry，不另造执行循环。

生成代码的`create_engine(db_path)`是CLI恢复原任务的工厂。业务配置、ToolSpec版本、Provider identity或模型变更后，用新业务命令／新环境；保留原冻结工厂和配置供旧任务恢复，不删除恢复保护来绕过definition_mismatch。外部网络或模型请求只在参与者明确配置后发生。

## 3. 自有业务审批与跨进程恢复

1. 提交自有业务测试输入，记录原command_id、Run和待批准参数，核对真实测试服务写入次数为0。错误参数必须拒绝，不为了通过而批准。
2. 退出整个Python／CLI进程，保留原数据库和冻结工厂。新进程用`relf --factory agent_app.runtime:create_engine --db .ralf/runs.sqlite --format text inspect RUN_ID`读取原任务；若生成项目使用其他数据路径，使用其实际原路径。
3. 检查原Action和摘要后运行inspect显示的批准命令，再在另一个进程运行原工厂resume。审批回执只确认决定保存，最终必须观察到succeeded及业务验证结果。
4. 重复相同批准命令和原提交，确认同一回执／Run，真实测试服务按effect_key只有一次业务效果。若原服务结果未知，保留unknown并按同一键核验，不能把重发写操作算作恢复。
5. 记录恢复前后状态、原回执和独立业务效果证据、每阶段耗时及实际求助。如果真实模型不能选对工具／参数，记录任务失败；离线改写答案不能代替该成绩。

完整命令参数顺序和原数据路径见[首用教程](getting-started.md)；`--db`／`--factory`／`--format`放在子命令前。等待超时或观察取消不取消业务Run；显式取消与实际handler停止、资源关闭分别核对，见[恢复排障](recovery-guide.md)。

## 完成判定

独立参与者应提交完整模板及脱敏的版本、命令、错误、审批与原业务结果证据。无求助、有限求助、需维护者修复、失败与未尝试分别记录；不要只报成功率。安装、模型替换、工具替换、审批、进程重启、重复操作都通过，才计为这一项自有业务接入通过，不能据此外推所有开发者或框架对等优势。

当前工程可按本地候选门槛单独冻结。没有独立参与者时保留待验证，不自动运行付费模型、不对外发邀请、不追加功能，也不重新打开已收口的性能或长期能力开发。
