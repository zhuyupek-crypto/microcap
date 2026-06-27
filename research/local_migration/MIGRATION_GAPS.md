# 迁移缺口报告

> 策略基线：`8290ca3` | 核心代码验收提交：`e97c857` | 开放P0=0 P1=0 P2=3 | 最终交付：本文件所在提交

---

## P0：阻止正确运行

### ~~GAP-012：`log.warn` 缺失~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-012~~ |
| 原优先级 | ~~P0~~ |
| 修复位置 | `engine/core.py` Engine 添加 `warn(self, msg): return self.warning(msg)` |
| 关闭证据 | 专线测试 test_log_warn_delegates_to_warning 通过：warn(\"test\")→warning(\"test\") 转发正确，返回值和日志输出均匹配 |
| 关闭日期 | TASK-MICROCAP-002 |

---

## P0：阻止正确运行

### ~~GAP-001：`position.value` 属性缺失~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-001~~ |
| 原优先级 | ~~P0~~ |
| 修复位置 | `engine/context.py` Position 类添加 `@property def value(self): return self.price * self.total_amount` |
| 关闭证据 | 专项测试 test_position_value_property 通过；price/total_amount 变化后 value 自动反映；调仓代码可直接读取当前持仓市值 |
| 关闭日期 | TASK-MICROCAP-002 |

### ~~GAP-002：`cash_flow.net_operate_cash_flow` 表缺失~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-002~~ |
| 原优先级 | ~~P0~~ |
| 修复位置 | `engine/core.py` namespace 添加 `cash_flow`；`engine/data_api.py` PIT读取 `cashflow.parquet` 的 `n_cashflow_act` → `net_operate_cash_flow` |
| 关闭证据 | PIT实证：000001.XSHE, 2023年报, release=2024-04-20, before=-23469M, on=-21382M；缺文件和缺字段测试均硬失败 |
| 关闭日期 | TASK-MICROCAP-002 |

### ~~GAP-003：`balance.total_liability` 表缺失~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-003~~ |
| 原优先级 | ~~P0~~ |
| 修复位置 | `engine/core.py` namespace 添加 `balance`；`engine/data_api.py` PIT读取 `balance.parquet` 的 `total_liab` → `total_liability` |
| 关闭证据 | PIT实证：000001.XSHE, 2023年报, release=2024-04-20, before liab=5114B, on liab=5243B；缺文件测试硬失败 |
| 关闭日期 | TASK-MICROCAP-002 |

### ~~GAP-004：`balance.total_assets` 表缺失~~ **已关闭**

| 项目 | 内容 |
|---|---|
| 编号 | ~~GAP-004~~ |
| 原优先级 | ~~P0~~ |
| 修复位置 | `engine/core.py` namespace 添加 `balance`；`engine/data_api.py` PIT读取 `balance.parquet` 的 `total_assets` |
| 关闭证据 | PIT实证：000001.XSHE, 2023年报, release=2024-04-20, before assets=5587B, on assets=5729B；缺字段测试硬失败 |
| 关闭日期 | TASK-MICROCAP-002 |

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
