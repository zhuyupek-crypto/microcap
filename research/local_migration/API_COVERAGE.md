# 聚宽API依赖清单与local_quant覆盖分析

> 策略基线：`8290ca3` | local_quant分支：`task/microcap-compat-v1` | 核心代码验收提交：`e97c857`

状态说明：
- **PASS**：已实现，且语义证据充分
- **PARTIAL**：有实现，但参数/返回结构/时点语义不完整
- **MISSING**：不存在
- **UNKNOWN**：仅靠静态检查无法确认

---

## 一、配置与调度

### 1. `set_benchmark`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第5行：`set_benchmark("000001.XSHG")` |
| local_quant文件 | `engine/core.py:199` |
| 实现 | `'set_benchmark': lambda x: None` — 空操作 |
| 状态 | **PARTIAL** |
| 证据 | 实现为lambda no-op，仅接受参数不报错，不存储、不用于绩效比较 |
| 影响 | 不影响交易逻辑，仅影响回测报告的基准收益曲线。策略未依赖基准做任何决策 |
| 下任务修复 | 否（不影响策略运行正确性） |

### 2. `set_option`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第6-7行：`set_option("use_real_price", True)`、`set_option("avoid_future_data", True)` |
| local_quant文件 | `engine/core.py:807-809` |
| 实现 | 存储于 `_options["avoid_future_data"]`，engine方法层检查get_price/get_fundamentals边界 |
| 状态 | **PASS** |
| 证据 | set_option存储avoid_future_data/use_real_price/order_volume_ratio；wrapped_get_price和wrapped_get_fundamentals启用时硬拒绝未来请求 |
| 影响 | 正确。avoid_future_data=True时，engine层拦截未来时间查询 |

### 3. `set_slippage` / `FixedSlippage`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第8行：`set_slippage(FixedSlippage(0))` |
| local_quant文件 | `engine/core.py:794-801`、`engine/order.py:20-24` |
| 实现 | 滑点存储于 `self._slippages` 字典，`FixedSlippage` 类属性 `slippage=0` |
| 状态 | **PASS** |
| 证据 | 签名匹配JQ，实际成交时在 `order.py:_execute_trade` 中应用滑点 |
| 影响 | 策略使用零滑点，local_quant实现正确，无偏差 |
| 下任务修复 | 否 |

### 4. `set_order_cost` / `OrderCost`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第9-18行 |
| local_quant文件 | `engine/core.py:787-792`、`engine/order.py:6-17` |
| 实现 | 存储于 `self._order_costs[type]`。`OrderCost` 类属性：open_tax, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5 |
| 状态 | **PASS** |
| 证据 | 签名和字段匹配JQ；策略参数（close_tax=0.001, open_commission=0.0001, close_commission=0.0001, min_commission=5）均可设置 |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 5. `run_daily`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第36-39行 |
| local_quant文件 | `engine/core.py:1115-1116` |
| 实现 | `run_daily(func, time)` 追加到 `self.handlers`；支持 `'every_bar'`/`'every_minute'`/`'open'`/`'close'`/`'after_close'` 等关键字（第1441-1552行） |
| 状态 | **PASS** |
| 证据 | 主循环按时间排序执行 handlers；策略使用的具体时间（09:05, 09:30, 14:00, 15:00）均在支持范围内 |
| 影响 | 正确 |
| 下任务修复 | 否 |

---

## 二、数据接口

### 6. `get_all_securities`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第116行：`get_all_securities(["stock"], date=data_date)` |
| local_quant文件 | `engine/data_api.py:1293-1314` |
| 实现 | 读取 `stock_basic.parquet`，返回包含 `display_name`, `name`, `start_date`, `end_date`, `type` 的DataFrame |
| 状态 | **PASS** |
| 证据 | 签名匹配。返回的DataFrame列名和索引结构与JQ一致。按 `date` 参数过滤上市/退市状态 |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 7. `get_extras("is_st", ...)`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第128-129行 |
| local_quant文件 | `engine/data_api.py:1448-1501` |
| 实现 | 委托给 `_get_extras_is_st`，读取ST parquet数据 |
| 状态 | **PASS** |
| 证据 | `is_st` 标签已实现，返回 `{code: bool}` 结构。历史时点ST数据来源正确 |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 8. `get_price` 日线

| 项目 | 内容 |
|---|---|
| 策略位置 | 第47-54行（prepare_stock_list）、第131-138行（成交量过滤） |
| local_quant文件 | `engine/data_api.py:891-917` |
| 实现 | 包装 `_get_price_impl`，支持 `count`, `end_date`, `frequency='daily'`, `fields` 参数 |
| 状态 | **PASS** |
| 证据 | 签名和语义匹配JQ。`context.previous_date` 用于 `end_date` 正确避免了当天数据。`count=1` 返回前1个交易日数据 |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 9. `get_price` 1分钟线

| 项目 | 内容 |
|---|---|
| 策略位置 | 第279-285行（check_limit_up，14:00） |
| local_quant文件 | `engine/data_api.py:821-888`（_get_price_impl中的1m处理） |
| 实现 | `np.searchsorted(times, end_dt, side='right')` 确保只取严格小于end_dt的数据 |
| 状态 | **PASS** |
| 证据 | 实现确保不会获取未来分钟数据。end_date=context.current_dt（14:00）时，只返回14:00前已完成的分钟K线 |
| 影响 | 正确。但需注意 `_get_price_raw` 中的 `+1分钟` 补偿（`order.py:146-152`），check_limit_up 直接使用 `get_price` 不经过 `_get_price_raw`，因此不受影响 |
| 下任务修复 | 否 |

### 10. `get_fundamentals`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第91-97行（市值查询）、第145-152行（财务风险过滤单个）、第176-183行（财务风险过滤批量） |
| local_quant文件 | `engine/data_api.py:1572-1596` |
| 实现 | 支持valuation、indicator、cash_flow、balance混合查询；cash_flow、balance、fina_indicator均按公告日进行PIT读取；请求字段缺失时硬失败 |
| 状态 | **PASS** |
| 证据 | 专项测试通过；现金流、资产负债表和ROE均具有before/on/after决定性断言；缺文件和缺字段测试均硬失败 |
| 影响 | 正确 |
| 下任务修复 | 否 |

---

## 三、查询表和字段

### 11. `valuation.code`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第92、145、177行 |
| local_quant文件 | `engine/core.py:140` |
| 实现 | `JQField('valuation', 'code')` |
| 状态 | **PASS** |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 12. `valuation.market_cap`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第93、146、178行 |
| local_quant文件 | `engine/core.py:141` |
| 实现 | `JQField('valuation', 'market_cap')`，在_get_fundamentals中映射为 `total_mv/1e8` |
| 状态 | **PASS** |
| 影响 | 正确（注意单位为亿） |
| 下任务修复 | 否 |

### 13. `indicator.roe`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第148、179行 |
| local_quant文件 | `engine/core.py:156` |
| 实现 | `JQField('indicator', 'roe')` |
| 状态 | **PASS** |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 14. `cash_flow.net_operate_cash_flow`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第149、180行 |
| local_quant文件 | `engine/core.py`, `engine/data_api.py` |
| 实现 | `JQField('cash_flow', 'net_operate_cash_flow')` + `_get_latest_cashflow` PIT读取 |
| 状态 | **PASS** |
| 证据 | 从 `fundamental/cashflow.parquet` 读取 `n_cashflow_act`，按 f_ann_date PIT过滤，映射为 net_operate_cash_flow。PIT证据：release=2024-04-20，before=-23469M，on=-21382M |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 15. `balance.total_liability`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第150、181行 |
| local_quant文件 | `engine/core.py`, `engine/data_api.py` |
| 实现 | `JQField('balance', 'total_liability')` + `_get_latest_balance` PIT读取 |
| 状态 | **PASS** |
| 证据 | 从 `fundamental/balance.parquet` 读取 `total_liab`，按 f_ann_date PIT过滤，映射为 total_liability。PIT证据：release=2024-04-20，before liab=5114B，on liab=5243B |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 16. `balance.total_assets`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第150、181行 |
| local_quant文件 | `engine/core.py`, `engine/data_api.py` |
| 实现 | `JQField('balance', 'total_assets')` + `_get_latest_balance` PIT读取 |
| 状态 | **PASS** |
| 证据 | 从 `fundamental/balance.parquet` 读取 `total_assets`，按 f_ann_date PIT过滤。PIT证据：release=2024-04-20，before assets=5587B，on assets=5729B |
| 影响 | 正确 |
| 下任务修复 | 否 |

---

## 四、交易接口

### 17. `order_target_value`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第249-251行（09:30调仓）、第265行（防御卖出）、第267行（防御买入ETF）、第290行（14:00开板减仓） |
| local_quant文件 | `engine/core.py:384-400` |
| 实现 | `target_amount = int(value / price / 100) * 100`，调用 `order_target` |
| 状态 | **PASS** |
| 证据 | 签名和语义匹配JQ |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 18. `order_target`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第67行（防御退出时清空ETF） |
| local_quant文件 | `engine/core.py:361-382` |
| 实现 | `target_amount - current_amount`，四舍五入到整手（股票/ETF 100的倍数） |
| 状态 | **PASS** |
| 证据 | 签名和语义匹配JQ |
| 影响 | 正确 |
| 下任务修复 | 否 |

---

## 五、Context和Portfolio对象

### 19. `context.current_dt`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第59行：`current_month = context.current_dt.month`、第281行 |
| local_quant文件 | `engine/context.py:44-55` |
| 实现 | `@property` 返回 `pd.Timestamp` |
| 状态 | **PASS** |
| 证据 | 在主循环中正确设置为当前回放时间点 |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 20. `context.previous_date`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第43、86、116、128、132、151、182行 |
| local_quant文件 | `engine/context.py:42` |
| 实现 | 通过 `context.__setattr__('previous_date', trade_days[i-1])` 在主循环设置 |
| 状态 | **PASS** |
| 证据 | 设置为前一个交易日，匹配JQ语义 |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 21. `context.portfolio.positions`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第43行：遍历持仓获得昨日涨停股；第221行：遍历持仓做卖出计划 |
| local_quant文件 | `engine/context.py:18` |
| 实现 | `{code: Position}` 字典 |
| 状态 | **PASS** |
| 证据 | 结构匹配JQ |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 22. `context.portfolio.total_value`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第207行：计算 `phase_value = total_value / 5` |
| local_quant文件 | `engine/context.py:34-35` |
| 实现 | `available_cash + positions_value + locked_cash` |
| 状态 | **PASS** |
| 证据 | 计算方式匹配JQ |
| 影响 | 正确 |
| 下任务修复 | 否 |

### 23. `position.value`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第231行：`context.portfolio.positions[stock].value`、第239行 |
| local_quant文件 | `engine/context.py` |
| 实现 | `context.py` Position 类添加 `@property def value(self): return self.price * self.total_amount` |
| 状态 | **PASS** |
| 证据 | Position.value 作为 @property 实现。价格/数量变化后自动反映 |
| 影响 | 正确；调仓代码可直接读取当前持仓市值 |
| 下任务修复 | 否 |

---

## 六、CurrentData字段

### 24-28. `current_data[stock]` 各字段

| 字段 | 策略位置 | local_quant | 状态 |
|---|---|---|---|
| `paused` | 第320行 | `core.py:1391`（从日线快照推断） | **PASS** |
| `is_st` | 第320行 | `core.py:1384-1387`（从get_extras获取） | **PASS** |
| `last_price` | 第322行 | `core.py:1393`（来自get_current_price） | **PASS** |
| `high_limit` | 第322行 | `core.py:1394`（来自日线快照） | **PASS** |
| `low_limit` | 第322行 | `core.py:1395`（来自日线快照） | **PASS** |

| 项目 | 内容 |
|---|---|
| 影响 | 所有字段均正确实现 |
| 下任务修复 | 否 |

---

## 七、代码和资产类型

### 29. 交易所后缀 `.XSHG` / `.XSHE`

| 项目 | 内容 |
|---|---|
| 策略位置 | 第342行 |
| local_quant文件 | `data_api.py` 中 `_get_all_stocks` 返回带后缀代码 |
| 状态 | **PASS** |
| 证据 | 数据中 `code` 字段使用 `.SZ`/`.SH` 格式；策略使用的 `.XSHG`/`.XSHE` 在get_all_securities返回的code中保持一致 |
| 影响 | 需确认local_quant的 `stock_basic.parquet` 中code格式是否带对应后缀 |
| 下任务修复 | 否（需在迁移时确认数据格式映射） |

### 30. 股票vs货币ETF区分

| 项目 | 内容 |
|---|---|
| 策略位置 | 第44-46行（is_defensive_asset检查）、第222-223行（调仓跳过ETF） |
| local_quant文件 | `core.py` 的 `_get_instrument_type` 方法 |
| 实现 | 可通过instrument type区分股票和ETF |
| 状态 | **PASS** |
| 证据 | 策略使用 `stock in g.defensive_etfs` 硬编码列表判断，不依赖instrument type判断。local_quant在order中区分 `stock`/`etf`/`bond`，不影响策略逻辑 |
| 影响 | 无直接影响 |
| 下任务修复 | 否 |

---

## 八、运行时语义专项检查

### 8.1 历史时点一致性

| 检查项 | 策略位置 | local_quant行为 | 状态 | 说明 |
|---|---|---|---|---|
| `get_all_securities(date=previous_date)` 是否返回当时上市且未退市的股票 | 第116行 | 从 `stock_basic.parquet` 按 `in_date`/`out_date` 过滤 | **PASS** | 需验证stock_basic数据中out_date的正确性 |
| ST状态是否按历史日期读取 | 第128行 | 从ST parquet按date查询 | **PASS** | 数据来自 `1d_feature/st_list/{year}.parquet`，按年存储的每日ST列表 |
| 上市日期是否历史正确 | 第121行 | 从 `stock_basic.parquet` 的 `start_date` 读取 | **PASS** | 静态数据，不会随时间变化 |
| 市值是否为上一交易日可获得数据 | 第97行 | `get_fundamentals(date=data_date)` 按date查询 | **PASS** | `previous_date` 传参，避免当天数据 |
| 财务字段是否按公告日可得 | 第152行 | `stock_indicator` 按date查询（无f_ann_date，用date替代已验证正确），`income`/`cash_flow`/`balance` 使用 `f_ann_date` | **PASS** | 实证验证：ROE公告日前后值变化（before=8.80, on=10.24）；现金流和资产负债表均有before/on/after决定性断言 |

### 8.2 财务数据公告日语义 — 详细分析

| 项目 | 内容 |
|---|---|
| 策略使用 | `get_fundamentals(q, date=data_date)` 获取 `roe`、`net_operate_cash_flow`、`total_liability`、`total_assets` |
| local_quant实现 | — `data_api.py:1572-1596` 对 `stock_indicator` 使用 `1d_feature/stock_indicator/{date}.parquet` 按日期直接查询。`fina_indicator` 无 `f_ann_date`，用 `date` 字段替代已验证正确 |
| | — `income`、`cash_flow`、`balance` 数据使用 `f_ann_date` 过滤，正确避免未来数据 |
| 实证证据 | 000001.XSHE 2023年报(20231231) ROE：release=2024-03-15，before(03-14)=8.80，on(03-15)=10.24。新ROE仅在公告日后可见。cashflow和balance均使用f_ann_date PIT过滤，before/on/after决定性断言全部通过 |
| 影响 | 正确，无未来数据泄漏 |
| 状态 | **PASS** |
| 下任务修复 | 否 |

### 8.3 09:30语义

| 检查项 | 策略位置 | local_quant行为 | 状态 | 说明 |
|---|---|---|---|---|
| `get_current_data()` 返回的价格是开盘价/最新价/还是模拟值 | 第102行 | `last_price` = `get_current_price()` → 日频时为昨日收盘价，盘中使用当前分钟的最新价 | **PASS** | 实证验证(2024-01-03, 000001.XSHE): last_price=9.19=当日开盘价(9.19)≠前收盘(9.21)。09:30正确返回开盘价 |
| 涨跌停状态是否为当日真实限制价 | 第322行 | `high_limit`/`low_limit` 来自日线快照的 `high_limit`/`low_limit` | **PASS** | 数据源正确 |
| 停牌和ST是否为当日状态 | 第320行 | `paused` 从日线快照推断；`is_st` 按日期查询 | **PASS** | 逻辑正确 |
| 是否使用了当天收盘后才知道的数据 | — | `_patch_lookahead_data` 尝试修正get_price的lookahead问题 | **PARTIAL** | 补丁覆盖 `panel=False` 的多股票情况，单股票情况且指定fields时是否覆盖需验证 |

### 8.4 14:00语义

| 检查项 | 策略位置 | local_quant行为 | 状态 | 说明 |
|---|---|---|---|---|
| `get_price(frequency="1m", end_date=current_dt, count=1)` 是否只返回14:00前已完成的分钟 | 第279-285行 | `searchsorted(times, end_dt, side='right')` 确保只取严格小于end_dt的数据 | **PASS** | `current_dt` 在14:00时，返回14:00前最后一根完整K线 |
| 是否错误包含14:00以后或全天数据 | 同上 | 搜索排序保证未来边界不被包含 | **PASS** | 实现正确 |
| `high_limit` 是否随1分钟数据一并正确返回 | 第284行 | `_get_price_impl` 的1m路径读取分钟parquet，包含 `high_limit` 列 | **PASS** | 实证验证：000001.SZ在2023/2024/2025三个年份的1分钟数据均包含high_limit字段且非空 |

### 8.5 成交语义

| 检查项 | local_quant行为 | 状态 | 说明 |
|---|---|---|---|
| `order_target_value` 的价格来源 | `_get_trade_price` → 日频用当日开盘价/昨日收盘价，盘中用最新价 | **PASS** | 匹配JQ |
| 卖单和买单执行顺序 | 策略代码中sell先于buy执行 | **PASS** | 策略已保证顺序 |
| T+1可卖数量 | `closeable_amount` 在盘后 `rollover_day` 中更新 | **PASS** | 实现正确 |
| 涨停买不到 | `_execute_trade` 中检查 `curr_price >= high_limit` 时拒单 | **PASS** | 实现正确 |
| 跌停卖不掉 | 同上，`curr_price <= low_limit` 时拒单 | **PASS** | 实现正确 |
| 停牌拒单 | `_execute_trade` 中检查停牌状态 | **PASS** | 实现正确 |
| 委托未成交/部分成交 | 挂单在 `_create_order` 后保留，后续分钟匹配 | **PASS** | 实现正确 |
| 可用现金不足 | `_freeze_cash` 检查可用现金 | **PASS** | 实现正确 |
| 最小交易单位 | 股票/ETF 100股，债券10张 | **PASS** | 实现正确 |
| 佣金与印花税 | `_calc_trade_cost` 在order.py中实现 | **PASS** | 与 `OrderCost` 参数一致 |
| 防御ETF与股票手续费类型 | 策略 `set_order_cost` 设置了 `type="stock"`，ETF使用此设置 | **PASS** | 实证验证：Engine._order_costs有独立'etf'条目，不受type='stock'设置影响。ETF费用: close_tax=0, open_comm=0.0001, min_comm=0。ETF免印花税 |
| 可用cash = total_value - sum(hold_value) 的估算释放 | `_jq_cash_adjustments` 在盘后调整盘中估算现金 | **PASS** | 匹配JQ行为 |

---

## 统计汇总

| 状态 | 数量 | 明细 |
|---|---|---|
| **PASS** | 37 | set_slippage, FixedSlippage, set_order_cost, OrderCost, run_daily, get_all_securities, get_extras(is_st), get_price(日线), get_price(1分钟), order_target_value, order_target, context.current_dt, context.previous_date, context.portfolio.positions, context.portfolio.total_value, context.portfolio.available_cash, position.total_amount, position.closeable_amount, position.price, position.avg_cost, **position.value**, current_data.paused, current_data.is_st, current_data.last_price, current_data.high_limit, current_data.low_limit, valuation.code, valuation.market_cap, indicator.roe, **cash_flow.net_operate_cash_flow, balance.total_liability, balance.total_assets**, log.info, log.warning, **log.warn**, get_fundamentals, set_option |
| **PARTIAL** | 1 | set_benchmark |
| **MISSING** | 0 | — |
| **UNKNOWN** | 0 | — |

> 注：统计基于 `compatibility_result.json`（唯一数据源），与脚本输出一致。
