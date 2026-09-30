# E08-A：响应丢失、持久幂等与结果查询

## 本步实验

```sh
uv run python -m hello_agent.sdk.e08_reliability.local
```

本步不调用模型，独立运行一笔固定模拟操作。它不接真实支付，也尚未与 E07 审批界面串联。E07 原入口保留。

1. 用固定操作 ID 提交 125.00 CNY 的模拟记账。
2. SQLite 事务提交后，主动抛出 TimeoutError，模拟响应丢失。
3. 调用方把结果视为未知，使用原 ID 查询。
4. 查到参数一致的记录，确认成功。
5. 为验证幂等，再用原 ID 与原参数重发，账本不增加。实际业务查到成功即可结束，不必再重发。

重复启动入口仍使用同一个固定实验 ID，所以首次新增一笔，之后新增零笔。该 ID 仅用于本实验；新业务操作应该有新 ID，同一业务操作的重试必须保留旧 ID。

## 核心规则

| 情况 | 行为 |
| --- | --- |
| ID 不存在 | 写入一笔模拟记录 |
| ID 已存在，参数一致 | 返回已有操作对应结果，不重复写入 |
| ID 已存在，参数不同 | 拒绝，不覆盖原记录 |
| 响应未收到 | 先按原 ID 查询，不能直接断言执行失败 |
| 参数一样但换了 ID | 视为新操作，会新增一笔 |

当前只存成功记录，一行就是一次模拟副作用。唯一键防止重复 ID；BEGIN IMMEDIATE 将查询和插入放在同一写事务内。参数使用 Pydantic 校验并比较收款人、整数分金额、币种和用途。

幂等与审批是不同约束：知道操作 ID 并不代表获得授权。本步只验证记账工具层，审批关联、未决状态和恢复需后续整合。

## 配置与代码

`.env` 中可设置 `LEDGER_PATH=.local/payments.sqlite3`，配置模型在 schemas/config.py，实例仍统一在 config/settings.py 初始化。入口因此沿用现有模型配置加载要求，但不会发送模型请求。`.local/` 已被 Git 忽略。

- schemas/ledger.py：PaymentOperation，绑定操作 ID 与付款参数。
- tools/ledger.py：持久记账、按 ID 查询和笔数统计。
- sdk/e08_reliability/local.py：固定故障实验。

## 验证（2026-09-30）

```sh
uv run python -m unittest discover -s tests -p "test_ledger.py"
```

4 项测试通过：同键同参只记一次、同键不同参数拒绝且不覆盖、提交后响应丢失并由新进程查询和重发、新键会产生新记录。真实本地入口首次运行从零笔变一笔，同键重发后仍为一笔。

本次只验证 E08-A，未重跑全套测试，未调用模型。TimeoutError 是显式故障注入，不是实际网络超时实验。

## 下一小步与边界

E08-A 中数据库错误直接抛出，不当作“未执行”，不自动重试。query 返回 None 只说明此时该数据库未查到成功记录，不能泛化成远端请求确定失败。E08-B 的有限重试策略见下文。

本地 SQLite 能把模拟副作用与幂等记录放在同一事务；真实远程付款和本地数据库不共享事务，不能把本实验当作跨系统恰好一次执行的保证。当前未验证并发压力、数据库损坏和真实进程崩溃恢复。

## E08-B：有限重试与结果未知（2026-09-30）

```sh
uv run python -m hello_agent.sdk.e08_reliability.retry before-timeout
uv run python -m hello_agent.sdk.e08_reliability.retry after-timeout
uv run python -m hello_agent.sdk.e08_reliability.retry query-unavailable
uv run python -m hello_agent.sdk.e08_reliability.retry always-timeout
uv run python -m hello_agent.sdk.e08_reliability.retry conflict
```

每次启动是独立的新实验，因此生成新 ID；同一次实验的所有重试共用原 ID 和参数。仍使用 LEDGER_PATH 对应的持久账本。本步不调用模型、不连接真实付款服务，也未整合人工审批。

### 策略

- 正常响应或查询结果与请求完全匹配：succeeded。
- 明确的 IdempotencyConflict：rejected，不查询、不重试。非法付款参数仍由 Pydantic 在构造请求时拒绝。
- TimeoutError / ConnectionError：先查询；查到匹配记录就结束，查到不匹配内容则 unknown 并停止。
- 查询成功但未查到记录：仅依赖底层幂等保证，用同 ID 同参数继续尝试，直到上限。
- 查询发生异常或执行发生未分类异常：unknown，停止重发。
- 最后一次执行仍超时：仍查询一次，未能确认就返回 unknown，不能写成确定失败。

`.env` 可设置 `RETRY_MAX_ATTEMPTS=3`，这是包含首次调用的总执行次数上限，不是额外重试次数；每次执行异常最多发起一次查询。结果包含操作 ID、状态、执行尝试数、查询次数和原因。

### 实测结果

默认三次上限，五个本地场景均正常结束：

| 场景 | 状态 | 执行 / 查询次数 | 实验侧账本 |
| --- | --- | --- | --- |
| 首次提交前超时 | succeeded | 2 / 1 | 新增 1 笔 |
| 提交成功后响应丢失 | succeeded | 1 / 1 | 新增 1 笔 |
| 提交成功后响应丢失，查询不可用 | unknown | 1 / 1 | 新增 1 笔 |
| 每次都超时 | unknown | 3 / 3 | 新增 0 笔 |
| 同 ID 参数冲突 | rejected | 1 / 0 | 只有 1 笔预置记录，冲突请求未记账 |

查询不可用场景最关键：实验者能直接检查本地账本，但执行策略只知道查询失败，因此保留 unknown。实际副作用和调用方已确认的信息不是一回事。

新增 7 项测试通过，原账本 4 项回归测试通过，共 11 项。覆盖查询确认后不重发、查询失败即停止、尝试上限含首次调用、最后一次仍查询、同 ID 参数不变、参数冲突、未分类异常及不匹配响应。未重跑全套测试。

本步的超时和连接错误仍为主动注入，没有实现对阻塞函数的实际计时中断、退避等待、总时限或真实网络验证；次数上限不等于耗时上限。重试策略只能用于本例这种明确支持幂等的执行接口，不能直接套到任意有副作用工具。
