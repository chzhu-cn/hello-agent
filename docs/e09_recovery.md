# E09-A：保存与恢复执行前的审批状态

## 本步范围

E01 保存对话历史；E09 保存程序走到哪里、当前操作是什么，以及是否获得批准。本步先处理 pending、approved、rejected 三种执行前状态，不执行付款，不写入账本，也不请求模型。

```sh
uv run python -m hello_agent.sdk.e09_recovery.local
```

首次启动创建固定参数的新提案并保存。再次启动读取原提案，保留 ID、参数和审批状态。交互选项：

- `q`：退出，保持已保存状态；输入结束和 Ctrl+C 也不将待审批改为拒绝。
- `a`：批准当前显示的提案，保存后退出；本步不自动执行。
- `r`：拒绝并保存退出；重启仍为 rejected，不能再次批准。
- `m`：修改收款人、金额和用途，生成新提案 ID，清除批准，保存后继续等待。

建议先运行并输入 q，再次启动观察同一提案；输入 a 后第三次启动，观察状态恢复为 approved，仍未执行。

## 保存什么

检查点包含版本号、提案 ID、付款参数、状态和批准绑定的 ID。通过 SavedProposal 和 SavedApproval 将持久化关键字段设为必填，缺少 ID 时不能自动生成一个新 ID 来掩盖文件损坏。

ApprovalState 增加一致性校验：approved/executed 必须绑定当前提案 ID；pending/rejected 不允许携带批准记录。加载损坏 JSON、缺失关键字段、未知版本或不一致批准记录时直接报错，不重建提案、不覆盖旧文件。

先写同目录临时文件并刷新，再替换目标文件；替换失败会清理临时文件，旧检查点保留。写入失败时入口终止，不继续使用仅存在于内存的新状态。临时文件与替换减少半写文件风险，不等于已经验证所有断电场景。

## 配置与代码

`.env` 中的 `CHECKPOINT_PATH` 默认是 `.local/approval-checkpoint.json`，实例在 config/settings.py 统一初始化。沿用现有配置加载方式，虽然不请求模型，仍需已有配置能正常加载。

- schemas/checkpoint.py：持久化检查点格式。
- tools/checkpoint.py：保存与加载。
- tools/approval.py 的 restore：恢复执行前状态，明确拒绝 executed。
- sdk/e09_recovery/local.py：独立交互入口。

E07 原入口仍保留，退出视为拒绝；E09 入口的退出用于模拟暂停，保留待审批状态。两者行为有意不同。

## 验证（2026-10-08）

```sh
uv run python -m unittest discover -s tests -p "test_checkpoint.py"
uv run python -m unittest discover -s tests -p "test_approval*.py"
```

6 项检查点测试、12 项审批回归测试全部通过。覆盖新进程恢复 pending、批准状态恢复后修改失效、拒绝状态恢复、损坏或不一致数据拒绝、替换失败保留旧文件，以及已执行状态不在本步范围内。

使用独立的 `.local/e09-validation.json`，连续启动三个真实本地进程，输入 q、a、q，观察同一个 ID 从 pending 保存到 approved 并成功恢复。没有写入付款账本。这是自动管道输入验证，用户手动体验尚待完成。未重跑全套测试。

## 下一步

E09-B 再处理工具调用前后中断：保存未决操作、复用 E08 原操作 ID 查询账本、确认成功后不重跑。审批检查点和账本不在一个事务里的时间窗口需要单独处理，不能只恢复一个 approved 字段就假定从未执行。

本步按单进程串行使用，检查点视为可信本地文件。字段校验不提供身份认证或防篡改能力；未支持多个实例同时修改，也未证明真实崩溃、断电后的恢复保证。

## E09-B：执行前后中断与未决操作恢复（2026-10-08）

先通过 E09-A 入口输入 a，保存一份已批准提案。执行入口使用该提案 ID 作为 E08 操作 ID，并将原参数存入独立执行检查点。

```sh
# 已批准后，正常执行并保存结果
uv run python -m hello_agent.sdk.e09_recovery.execution execute

# 恢复已有执行检查点，只查询，不重新调用工具
uv run python -m hello_agent.sdk.e09_recovery.execution recover
```

`.env` 新增 `CHECKPOINT_EXECUTION_PATH=.local/execution-checkpoint.json`。审批文件、执行文件和账本路径应在恢复时保持一致；新提案使用新的执行文件路径，不能覆盖另一提案的执行记录。

### 执行顺序

```text
读取 approved 审批 → 保存 approved 执行检查点
→ 保存 executing → 调用幂等账本 → 保存 succeeded 与完整结果
```

执行检查点保存批准 ID、原参数、阶段及已确认结果。保存 executing 失败就不会调用工具。若工具已成功但保存结果失败，文件仍是 executing，重启后可以按原 ID 查询账本补回结果。成功结果必须匹配提案 ID 和参数。

恢复规则：

- succeeded：直接使用保存的结果，不查询也不执行。
- executing / unknown：按原操作 ID 查询；匹配则保存 succeeded，查不到匹配结果或查询失败则保留 unknown。
- approved：仅恢复尚未启动状态，recover 不自动执行，需显式 execute。
- rejected：保持终止状态，不重新执行。

同 ID 参数冲突由账本明确拒绝，保存 rejected。对未决状态，本步不自动重发；E08 的幂等重试策略不意味着每次恢复都必须执行重试。

### 真实进程退出实验

为一份新的已批准提案设置独立的执行检查点后，可注入中断：

```sh
uv run python -m hello_agent.sdk.e09_recovery.execution execute --crash-at after-call
uv run python -m hello_agent.sdk.e09_recovery.execution recover
```

after-call 在账本提交之后、结果检查点保存之前立即退出当前实验进程，退出码 73。恢复查询可确认成功，账本仍是一笔。before-call 在保存 executing 之后、调用工具之前退出；恢复查不到结果，会保留 unknown，不自动调用工具。若检查点已是终止状态，故障开关不会重新运行工具。

两种实验说明同一个 executing 文件可能对应“还没调用”或“已成功记账”，不能仅靠执行阶段推断副作用。注入点处的进程退出已验证；这不等于证明任意指令位置、断电或多进程并发下的恢复保证。

### 验证

```sh
uv run python -m unittest discover -s tests -p "test_recovery.py"
```

8 项新增测试通过：未批准不能准备执行、正常成功及重复恢复不执行、调用前/提交后真实子进程退出、查询失败后再次查询恢复、工具前保存失败不调用、结果保存失败后补回成功、新提案不能覆盖旧执行检查点。另有 6 项 E09-A 和 4 项账本回归测试通过，共 18 项。本次未调用模型、未重跑全套测试，用户手动体验与回顾仍待完成。

本步使用可信本地审批文件与单进程执行。恢复执行前不重新请求模型，也不让模型重写参数。已执行结果保存到新执行检查点，E09-A 审批文件仍作为批准快照，E07 的内存 execute 方法未接入此入口。
