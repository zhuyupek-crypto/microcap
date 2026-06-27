# 迁移缺口报告

> 策略基线：`8290ca3` | local_quant HEAD：`2a3167ef`

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

### GAP-005：09:30价格语义差异

| 项目 | 内容 |
|---|---|
| 编号 | GAP-005 |
| 优先级 | **P1** |
| 涉及接口 | `get_current_data().last_price` |
| 聚宽策略中的使用位置 | 第102行（`can_buy_today`）、第103行（可买判断）、第316-323行 |
| local_quant当前行为 | `current_data.last_price` 来自 `get_current_price()`。日频模式下该价格可能是昨日收盘价；盘中模式为当前分钟最新价 |
| 预期正确行为 | 在09:30调用 `get_current_data().last_price` 时，JQ返回开盘价（集合竞价结果）。local_quant需确认该时点的返回价格 |
| 可能导致的偏差 | 若返回昨日收盘价而非开盘价，可能造成以下差异：1）涨停板判断：昨日收盘价接近涨停价时，开盘价可能已经打开涨停，但使用昨日收盘价会误判为未涨停；2）目标股数计算：`order_target_value` 使用价格计算目标股数，价格差异导致股数差异 |
| 建议修复位置 | `engine/core.py:1393` `get_current_price()` 的日频路径 |
| 建议测试 | 给定一个9:30的回测场景，验证 `last_price` 等于当日开盘价而非昨日收盘价 |

### GAP-006：财务数据公告日语义不完整

| 项目 | 内容 |
|---|---|
| 编号 | GAP-006 |
| 优先级 | **P1** |
| 涉及接口 | `get_fundamentals` 的 `date` 参数 |
| 聚宽策略中的使用位置 | 第97行、第152行、第183行 |
| local_quant当前行为 | `stock_indicator` 按日期直接读取，不使用 `f_ann_date`。`income` 数据正确使用 `f_ann_date`。`roe` 字段来自 `stock_indicator` |
| 预期正确行为 | ROE等基本面指标应使用最新可得的公告数据，即在查询日期之前已披露的财报数据 |
| 可能导致的偏差 | ROE可能使用了未来公告日才可知的数据。如果某公司在2024年4月30日披露一季报，而`stock_indicator` 在4月1日已包含一季报ROE数据，则4月1日的策略选股将基于不可得的未来信息 |
| 建议修复位置 | `engine/data_api.py:1572-1596` 对 `stock_indicator` 增加 `f_ann_date` 过滤逻辑 |
| 建议测试 | 构造一个跨财报披露日的场景：验证某股票在披露日前后 `get_fundamentals` 返回的ROE是否一致 |

### GAP-007：set_option 静默忽略未来数据检查

| 项目 | 内容 |
|---|---|
| 编号 | GAP-007 |
| 优先级 | **P1** |
| 涉及接口 | `set_option("avoid_future_data", True)` |
| 聚宽策略中的使用位置 | 第7行 |
| local_quant当前行为 | 静默忽略 |
| 预期正确行为 | 当 `get_price` 或 `get_fundamentals` 可能返回未来数据时应发出警告或阻止 |
| 可能导致的偏差 | 由于设置了 `avoid_future_data=True` 但被忽略，任何未来数据问题不会被检测到 |
| 建议修复位置 | `engine/core.py:807-809` 增加对 `avoid_future_data` 的处理（至少记录警告日志） |
| 建议测试 | 无需专门测试 |

### GAP-008：防御ETF手续费类型

| 项目 | 内容 |
|---|---|
| 编号 | GAP-008 |
| 优先级 | **P1** |
| 涉及接口 | `set_order_cost(OrderCost(...), type="stock")` 对ETF适用 |
| 聚宽策略中的使用位置 | 第9-18行、第267行（买入ETF） |
| local_quant当前行为 | 策略对所有资产使用 `type="stock"` 的费用设置。ETF交易（特别是货币ETF `511880.XSHG`）的佣金结构可能与股票不同 |
| 预期正确行为 | 货币ETF买卖通常免印花税，佣金费率可能低于股票 |
| 可能导致的偏差 | 如果local_quant对ETF使用不同的费用类型（如 `type="etf"`），而策略未设置该类型，ET交易可能使用默认费用导致偏差。如果local_quant统一使用 `type="stock"`，则无异 |
| 建议修复位置 | 迁移时确认local_quant的ETF费用处理方式，或为ETF类型单独设置费用 |
| 建议测试 | 对比测试相同条件下ETF交易费用是否一致 |

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

## 缺口统计

| 优先级 | 数量 | 编号 |
|---|---|---|
| **P0** | 4 | GAP-001, GAP-002, GAP-003, GAP-004 |
| **P1** | 4 | GAP-005, GAP-006, GAP-007, GAP-008 |
| **P2** | 3 | GAP-009, GAP-010, GAP-011 |
| **合计** | **11** | |
