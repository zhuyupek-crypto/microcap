# 迁移缺口报告

> 策略基线：`8290ca3` | local_quant HEAD：`2a3167ef`

---

## P0：阻止正确运行

### GAP-012：`log.warn` 缺失

| 项目 | 内容 |
|---|---|
| 编号 | GAP-012 |
| 优先级 | **P0** |
| 涉及接口 | `log.warn` |
| 聚宽策略中的使用位置 | 第154行：`log.warn("risk filter skipped for %s: %s" % (stock, e))`；第186行：`log.warn("batch risk filter skipped: %s" % e)` |
| local_quant当前行为 | `log` 对象（Engine 自身）仅有 `info()`、`warning()`、`debug()` 方法。`warn()` 方法不存在。调用 `log.warn()` 将抛出 `AttributeError` |
| 预期正确行为 | `log.warn()` 应为 `log.warning()` 的别名，与聚宽一致 |
| 执行链分析 | `cash_flow`/`balance` 查询失败 → 策略进入 `except` 块 → 调用 `log.warn(...)` → **`AttributeError`** → 策略中断。注意：此缺口与 GAP-002/003/004 交互。即使修复了 `cash_flow`/`balance` 表，其他查询异常仍可能触发此路径 |
| 建议修复位置 | `engine/core.py` 的 `Logger` 类添加 `def warn(self, msg): return self.warning(msg)` |
| 建议测试 | 调用 `log.warn("test")` 验证不抛出异常且等效于 `log.warning` |

---

## P0：阻止正确运行

### GAP-001：`position.value` 属性缺失

| 项目 | 内容 |
|---|---|
| 编号 | GAP-001 |
| 优先级 | **P0** |
| 涉及接口 | `context.portfolio.positions[stock].value` |
| 聚宽策略中的使用位置 | 第231行（`rebalance_to_aggregate_targets`）：`current_value = context.portfolio.positions[stock].value`；第239行：`context.portfolio.positions[stock].value if stock in context.portfolio.positions else 0.0` |
| local_quant当前行为 | `Position` 类（`engine/context.py:6-11`）无 `value` 属性，访问将抛出 `AttributeError` |
| 预期正确行为 | `value = self.price * self.total_amount`，即持仓市值 |
| 可能导致的偏差 | 运行时直接异常，调仓逻辑无法执行 |
| 建议修复位置 | `engine/context.py` Position类添加 `@property def value(self): return self.price * self.total_amount` |
| 建议测试 | 单元测试：创建Position实例，设置price和total_amount，验证value返回正确乘积 |

### GAP-002：`cash_flow.net_operate_cash_flow` 表缺失

| 项目 | 内容 |
|---|---|
| 编号 | GAP-002 |
| 优先级 | **P0** |
| 涉及接口 | `cash_flow.net_operate_cash_flow` |
| 聚宽策略中的使用位置 | 第149行、第180行（`risk_filter_ok` 和 `build_risk_filter_map`） |
| local_quant当前行为 | `cash_flow` 表在 `core.py:139-162` 中未创建。查询时 `JQQuery` 会抛出 `AttributeError` |
| 预期正确行为 | 从 `fundamental/cashflow.parquet` 读取 `net_operate_cash_flow`（即经营性现金流净额），并按 `f_ann_date` 过滤获得公告日可得数据 |
| 可能导致的偏差 | 策略 `try/except`（第153-154行）捕获异常后默认返回True（通过风险过滤）。导致本应被过滤的高风险股票（高负债+负现金流且低ROE）被纳入候选池 |
| 建议修复位置 | `engine/core.py` 添加 `cash_flow` 表的 `JQField` 定义；`engine/data_api.py` 的 `get_fundamentals` 中添加 `cash_flow` 数据读取路径 |
| 建议测试 | 对比测试：构造一个应被风险过滤拒绝的股票，验证在local_quant中因异常被放行 |

### GAP-003：`balance.total_liability` 表缺失

| 项目 | 内容 |
|---|---|
| 编号 | GAP-003 |
| 优先级 | **P0** |
| 涉及接口 | `balance.total_liability` |
| 聚宽策略中的使用位置 | 第150行、第181行（计算资产负债率） |
| local_quant当前行为 | `balance` 表未创建。查询时 `JQQuery` 抛出异常 |
| 预期正确行为 | 从 `fundamental/balance.parquet` 读取 `total_liability`（总负债），按 `f_ann_date` 过滤 |
| 可能导致的偏差 | 同GAP-002，异常被捕获后默认放行。资产负债率阈值95%的风险过滤失效 |
| 建议修复位置 | 同GAP-002，添加 `balance` 表定义和数据读取路径 |
| 建议测试 | 同GAP-002 |

### GAP-004：`balance.total_assets` 表缺失

| 项目 | 内容 |
|---|---|
| 编号 | GAP-004 |
| 优先级 | **P0** |
| 涉及接口 | `balance.total_assets` |
| 聚宽策略中的使用位置 | 第150行、第181行（计算资产负债率） |
| local_quant当前行为 | 同GAP-003，`balance` 表未创建 |
| 预期正确行为 | 从 `fundamental/balance.parquet` 读取 `total_assets`（总资产） |
| 可能导致的偏差 | 同GAP-003。`total_assets <= 0` 检查也会失效，因为 `total_assets` 获取不到时变为 `None`，触发 `return False`（拒绝），但这是从except分支返回的默认True，所以实际上两者抵消效果不确定 |
| 建议修复位置 | 同GAP-002 |
| 建议测试 | 同GAP-002 |

---

## P1：能够运行，但结果可能明显偏离聚宽

### ~~GAP-005：09:30价格语义差异~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-005~~ |
| 优先级 | ~~P1~~ → **已关闭** |
| 涉及接口 | `get_current_data().last_price` |
| 关闭证据 | 实证测试 `test_current_data_0930_last_price_uses_open` 通过：Engine实例化后设current_dt=2024-01-03 09:30，000001.XSHE的last_price=9.19=当日开盘价(9.19)≠前收盘(9.21)。local_quant在09:30正确返回开盘价，语义与聚宽一致 |
| 关闭日期 | TASK-MICROCAP-001B |

### ~~GAP-006：财务数据公告日语义不完整~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-006~~ |
| 优先级 | ~~P1~~ → **已关闭** |
| 涉及接口 | `get_fundamentals` 的 `date` 参数 |
| 关闭证据 | 实证测试：fina_indicator.date字段天然PIT。000001.XSHE 2023年报(20231231) ROE：release=2024-03-15，before(03-14)=8.80，on(03-15)=10.24。新ROE仅在公告日后可见。cashflow和balance均使用f_ann_date PIT过滤。 |
| 关闭日期 | TASK-MICROCAP-002B |
| 备注 | fina_indicator无f_ann_date，用date字段替代。实证确认无未来数据泄漏。 |

### ~~GAP-007：set_option 静默忽略未来数据检查~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-007~~ |
| 优先级 | ~~P1~~ → **已关闭** |
| 涉及接口 | `set_option("avoid_future_data", True)` |
| 关闭证据 | wrapped_get_price和wrapped_get_fundamentals在avoid_future_data=True时硬拒绝未来时间查询(RuntimeError)。测试验证：get_price with future end_date raises RuntimeError；关闭option后允许。 |
| 关闭日期 | TASK-MICROCAP-002B |
| 备注 | 同时存储use_real_price和order_volume_ratio。未知option记录警告。 |

### ~~GAP-008：防御ETF手续费类型~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-008~~ |
| 优先级 | ~~P1~~ → **已关闭** |
| 涉及接口 | `set_order_cost(OrderCost(...), type="stock")` 对ETF适用 |
| 关闭证据 | 实证测试 `test_511880_uses_etf_cost_model` 通过：Engine._order_costs有独立'etf'条目(close_tax=0, open_comm=0.0001, min_comm=0)，不受 type='stock' 设置影响。ETF自动免印花税 |
| 关闭日期 | TASK-MICROCAP-001B |

---

## P2：不影响首轮信号对齐，但影响实盘真实性

### GAP-009：部分成交处理

| 项目 | 内容 |
|---|---|
| 编号 | GAP-009 |
| 优先级 | **P2** |
| 涉及接口 | `order_target_value` 部分成交 |
| 聚宽策略中的使用位置 | 间接（策略依赖目标仓位调整，部分成交导致实际持仓偏离目标） |
| local_quant当前行为 | 订单在下一分钟继续尝试成交 |
| 预期正确行为 | 尾盘未成交订单如何处理？JQ行为需确认 |
| 可能导致的偏差 | 部分成交导致实际仓位与目标仓位持续偏离 |
| 建议测试 | 待信号对齐后再评估 |

### GAP-010：市场冲击成本

| 项目 | 内容 |
|---|---|
| 编号 | GAP-010 |
| 优先级 | **P2** |
| 涉及接口 | `set_slippage(FixedSlippage(0))` |
| 说明 | 策略使用零滑点，实际交易有冲击成本。微盘股流动性差，冲击成本显著 |
| 影响 | 回测收益可能显著高于实盘 |

### GAP-011：连续跌停退出

| 项目 | 内容 |
|---|---|
| 编号 | GAP-011 |
| 优先级 | **P2** |
| 说明 | 策略不处理连续跌停场景。微盘股小市值特征使其在下跌行情中更容易出现连续跌停 |
| 影响 | 回测中可能高估了跌停股票的卖出能力 |

---

## 缺口统计（TASK-MICROCAP-002C 最终状态）

| 优先级 | 开放 | 已关闭 | 编号(开放) |
|---|---|---|---|
| **P0** | 0 | 5 | — |
| **P1** | 0 | 4 | — |
| **P2** | 3 | 0 | GAP-009, GAP-010, GAP-011 |
| **合计** | **3** | **9** | |
