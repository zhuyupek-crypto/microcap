# 审计副本语义差异报告

## 源文件
`微盘股-母版-20260627.py` → `微盘股-母版-20260627-audit.py`

## SHA-256 校验
- 源文件: `F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6`
- 审计副本: 不同（因新增日志代码）

## 差异类型：仅增不减

所有差异均为**追加代码**，未修改任何原始代码行。

### 追加清单

| 位置 | 追加内容 | 影响 |
|---|---|---|
| 文件顶部 (L3-L34) | `_audit_log()`, `_write_audit_log()`, `_AUDIT_LOG` 列表 | 新增结构化JSON日志器 |
| `initialize()` 末尾 | `_audit_log("initialize", ...)` | 记录初始化参数 |
| `prepare_stock_list()` 循环内 | `_audit_log("yesterday_HL_check", security=stock, ...)` | 记录每只股票的涨跌停判断 |
| `prepare_stock_list()` 末尾 | `_audit_log("yesterday_HL_list_result", ...)` | 记录昨日涨停名单 |
| `trade()` 入口 | `_audit_log("trade_enter", g_days_before=..., ...)` | 记录进入交易函数的状态 |
| `trade()` 防御模式分支 | `_audit_log("trade_defensive_enter/...")` | 记录防御模式切换 |
| `trade()` due_offsets 计算后 | `_audit_log("trade_due_offsets", ...)` | 记录到期相位 |
| `trade()` 相位目标选择后 | `_audit_log("trade_phase_target_selected", ...)` | 记录新选择的标的 |
| `trade()` 再平衡前 | `_audit_log("pre_rebalance_position", ...)` | 记录每只股票的相位成员 |
| `trade()` 无到期时 | `_audit_log("trade_no_due_offsets")` | 记录无到期日 |
| `trade()` d.gdays 递增后 | `_audit_log("trade_exit", ...)` | 记录日计数 |
| `select_smallest_market_cap()` 各分支 | `_audit_log("select_mcap_*", ...)` | 记录选股路径 |
| `aggregate_target_values()` 全程 | `_audit_log("aggregate_target_*", ...)` | 记录目标值计算 |
| `rebalance_to_aggregate_targets()` 卖出决策 | `_audit_log("sell_decision", ...)` | 记录每只股票的卖出计划决策 |
| `rebalance_to_aggregate_targets()` 买入决策 | `_audit_log("buy_decision", ...)` | 记录买入计划 |
| `rebalance_to_aggregate_targets()` 再平衡计划 | `_audit_log("rebalance_plan", ...)` | 记录最终买卖计划 |
| `rebalance_to_aggregate_targets()` 下单时 | `order_obj = order_target_value(...)`, `_audit_log("order_target_value", ...)` | 记录下单返回值 |
| `check_limit_up()` 开板时 | `_audit_log("check_limit_up_open", ...)` | 记录开板卖出 |
| `report_plan()` 末尾 | `_audit_log("report_plan_summary", ...)`, `_write_audit_log()` | 记录日终摘要 + 保存日志 |

### 不修改的行

- `def initialize(context):` → 函数签名未变
- `set_benchmark(...)`, `set_option(...)`, `set_slippage(...)` → 参数未变
- `g.days = 0`, `g.stocknum = 10`, 所有 g. 变量 → 初始值未变
- `run_daily(...)` 注册 → 时间与函数未变
- `while`/`for`/`if`判断条件 → 完全未变
- `order_target_value(stock, target_value)` → 原调用行改为接收返回值 `order_obj = order_target_value(...)`，但**仅增加变量接收，未改变参数或调用次数**
- `target_value <= 0` 判断逻辑 → 未变
- `current_value > target_value and stock in g.yesterday_HL_list` → 未变
- `can_sell_today()` / `can_buy_today()` → 未变
- `is_common_stock()` / `is_defensive_asset()` → 完全未变

### 证明无交易逻辑变化

1. **变量接收不改语义**: `order_obj = order_target_value(...)` 中 `order_obj` 未被用于任何控制流判断，仅传递给 `_audit_log()` 提取字段
2. **日志函数不修改状态**: `_audit_log()` 仅追加到 `_AUDIT_LOG` 列表（`append` 操作），不修改任何全局变量或交易策略对象
3. **调用次数不变**: 所有 `order_target_value(...)` 的调用次数与原始策略相同——每次调用仅增加一个变量接收，不影响 Polyfill 引擎的执行
4. **控制流不变**: 所有 `if`/`for`/`continue`/`break`/`return` 语句的位置、条件和顺序与原始策略完全相同
