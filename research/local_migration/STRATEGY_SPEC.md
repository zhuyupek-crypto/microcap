# 微盘股策略冻结说明

基于提交 `8290ca3` 中 `微盘股-母版-20260627.py`，忠实描述当前代码逻辑。

---

## 固定参数

| 参数 | 值 | 说明 |
|---|---|---|
| `phase_cycle` | 15 | 完整调仓周期天数 |
| `phase_offsets` | [0, 3, 6, 9, 12] | 五个错位批次的偏移量 |
| `stocknum` | 10 | 每个批次的目标股票数 |
| `min_list_days` | 375 | 最小上市天数 |
| `defensive_months` | [1, 4] | 防御月份（1月、4月） |
| `defensive_etfs` | ["511880.XSHG"] | 防御目标资产（货币ETF） |
| `use_risk_filter` | True | 是否启用财务风险过滤 |
| `trade_enabled` | True | 是否实际执行交易 |

---

## 调度

| 时间 | 处理函数 | 行为 |
|---|---|---|
| 09:05 | `prepare_stock_list` | 检查昨日涨停持仓，记录到 `g.yesterday_HL_list` |
| 09:30 | `trade` | 选股/防御判断/调仓 |
| 14:00 | `check_limit_up` | 昨日涨停股开板后降至目标仓位 |
| 15:00 | `report_plan` | 日志输出当天计划和状态 |

### 细节说明

- 函数执行顺序由 `run_daily` 注册到 `handlers` 列表，按时间排序统一执行；
- 14:00 检查时，策略调用 `get_price(frequency="1m", count=1, end_date=context.current_dt)` 获取14:00前的最后一根1分钟K线；
- 15:00 输出为纯日志，不执行任何交易。

---

## 选股流程

严格按照代码中 `select_smallest_market_cap` 的调用顺序：

1. **全市场股票**：`get_all_securities(["stock"], date=data_date)` 获取历史时点全部股票。
2. **过滤非普通股**：`is_common_stock` 排除代码以 `688`、`689`、`4`、`8`、`9` 开头的股票，且只保留 `.XSHG` 和 `.XSHE` 后缀。
3. **上市天数过滤**：剔除上市不满 `min_list_days`（375天）的股票。
4. **ST过滤**：`get_extras("is_st", pool, start_date=data_date, end_date=data_date)` 剔除历史时点ST。
5. **成交量过滤**：`get_price(..., fields="volume")` 剔除上一交易日成交量为零的股票。
6. **市值获取**：`get_fundamentals(query(valuation.code, valuation.market_cap).filter(...), date=data_date)` 获取上一交易日总市值。
7. **市值排序**：按总市值升序排列候选股票。
8. **财务风险过滤**：`build_risk_filter_map` 对候选逐一检查：
   - 总资产缺失或 <=0 → 拒绝
   - 资产负债率 >= 95% → 拒绝
   - ROE <= -50 且 经营现金流净额 <= -1e8 → 拒绝
   - 以上过滤称为"弱财务尾部风险过滤"。
9. **可买状态检查**：`can_buy_today` 通过 `get_current_data()` 检查：
   - 停牌（`paused`）→ 不可买
   - ST（`is_st`）→ 不可买
   - 涨停（`last_price >= high_limit`）→ 不可买
   - 跌停（`last_price <= low_limit`）→ 不可买
10. **取前N只**：每个批次取前 `stocknum`（10只）目标股票。

---

## 组合结构

### 错位批次

- 5个批次，偏移量分别为 0、3、6、9、12 天；
- 每个批次占组合理论资金的 `1/5 = 20%`；
- 每批目标持有10只股票；
- 单只股票在一个批次的权重为 `20% / 10 = 2%`；
- 同一股票出现在多个批次时，目标权重累加（如同时出现在2个批次则为4%）。

### 调仓时机

- 每3个交易日有一个批次到期更新（`due_offsets`计算）；
- 正常情况单个批次持有约15个交易日。

### 目标仓位计算

`aggregate_target_values`：
```
phase_value = portfolio.total_value / 5
stock_value = phase_value / 10
target_stock = sum(stock_value for each phase containing this stock)
```

### 调仓逻辑（09:30）

卖出顺序优先于买入：

1. 遍历当前持仓，对非防御资产：
   - 目标为0且不在昨日涨停名单中 → 卖出
   - 目标为0但在昨日涨停名单中 → 跳过（等14:00处理）
   - 当前值 > 目标值且在昨日涨停名单中 → 跳过
   - 当前值 > 目标值且不在涨停名单 → 卖出至目标
2. 遍历目标持仓，当前值 < 目标值且可买 → 买入至目标。
3. `sell` 先执行，`buy` 后执行。

---

## 防御逻辑

来源：`switch_to_defensive` 函数

### 进入条件

- `in_defensive_mode = False` 且当前月份在 `defensive_months`（1月、4月）中。

### 进入行为

1. 遍历持仓，对所有非防御资产且可卖出的 → 清仓（目标值0）。
2. 清空所有phase的目标股票列表。
3. 买入防御ETF（`511880.XSHG`），每只ETF目标金额为 `total_value / len(defensive_etfs)`。
4. 设置 `in_defensive_mode = True`。
5. 注意：**防御状态以月份判断设置为条件**，不以订单是否实际成交为条件。

### 退出条件

- `in_defensive_mode = True` 且当前月份不在 `defensive_months` 中。

### 退出行为

1. 卖出所有防御ETF（`order_target(etf, 0)`）。
2. 设置 `in_defensive_mode = False`。
3. 当天后续的 `trade` 函数会正常执行选股和调仓。

### 关键细节

- 防御模式下 `trade` 函数在 `switch_to_defensive` 调用后立即 `return`，不执行选股和正常调仓；
- 防御模式下 `check_limit_up` 直接 `return`，不处理昨日涨停；
- 防御模式退出当天，`trade` 会执行选股调仓（因为 `in_defensive_mode` 已为 False）；
- `g.days` 计数器在防御期间**是否暂停**？查看代码：`switch_to_defensive` 在 `trade` 中被调用后 `return`，所以 `g.days += 1` 不会执行。防御期间 `trade` 继续被调用但直接 `return`，因此 `g.days` 在防御期间**不递增**。
- 退出防御当天 `g.days += 1` 会执行，但偏移计算使用 `(g.days + offset) % phase_cycle`，由于防御期间 `days` 已停滞，重新选股时机与进入防御时的计数器一致。

---

## 关键常量

| 常量 | 位置（行） | 值 |
|---|---|---|
| 基准 | 5 | 000001.XSHG（上证指数） |
| 滑点 | 8 | FixedSlippage(0) |
| 佣金 | 9-18 | 买入万1，卖出万1+千1印花税，最低5元 |
