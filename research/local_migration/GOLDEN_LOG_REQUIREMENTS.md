# 黄金对照日志需求

下一阶段需要从聚宽（JQ）导出的对照数据，用于与 local_quant 回测结果逐日逐项对比。

---

## 输出格式

建议使用 **JSON Lines (`.jsonl`)** 格式，每天一行，每行为一个 JSON 对象。

```jsonl
{"date": "2024-01-02", "previous_date": "2023-12-29", ...}
{"date": "2024-01-03", "previous_date": "2024-01-02", ...}
```

也可使用 CSV，但结构化数据（列表、字典）需序列化为 JSON 字符串。

---

## 每日对照字段

### 基本信息

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | str (YYYY-MM-DD) | 当前交易日 |
| `previous_date` | str (YYYY-MM-DD) | 前一交易日 |
| `days` | int | `g.days` 计数器值 |
| `defensive` | bool | `g.in_defensive_mode` 值 |
| `due_offsets` | list[int] | 当天到期的 phase 偏移量列表 |
| `trade_enabled` | bool | `g.trade_enabled` 值 |

### 选股全流程日志

| 字段 | 类型 | 说明 |
|---|---|---|
| `total_securities` | int | `get_all_securities(["stock"], date=previous_date)` 返回数量 |
| `common_stock_count` | int | `is_common_stock` 过滤后数量 |
| `min_list_days_count` | int | 上市>=375天过滤后数量 |
| `st_removed_count` | int | ST过滤后数量 |
| `volume_zero_removed_count` | int | 成交量=0过滤后数量 |
| `top_30_mcap` | list[{"code":str, "market_cap":float}] | 市值排序前30的股票代码和市值（亿） |
| `final_candidate_count` | int | 最终候选池数量 |

### 财务风险过滤

| 字段 | 类型 | 说明 |
|---|---|---|
| `risk_filter_results` | list[{"code": str, "passed": bool, "reason": str}] | 每只股票的过滤结果和原因（debt_to_assets>95, roe<=-50 and ocf<=-1e8, total_assets_none, ok） |

### Phase目标

| 字段 | 类型 | 说明 |
|---|---|---|
| `phase_targets` | dict[str, list[str]] | 每个 offset 的目标股票列表，如 `{"0": ["000001.SZ", ...], "3": [], ...}` |
| `new_targets_per_phase` | dict[str, list[str]] | 当天新增的 phase 目标（仅在 due_offsets 中的 phase 有数据） |

### 聚合目标

| 字段 | 类型 | 说明 |
|---|---|---|
| `aggregate_targets` | list[{"code":str, "target_value":float}] | 聚合后的目标权重和金额 |
| `total_target_value` | float | 目标总金额 |

### 09:30 当前数据

| 字段 | 类型 | 说明 |
|---|---|---|
| `current_data_0930` | list[{"code": str, "last_price": float, "high_limit": float, "low_limit": float, "paused": bool, "is_st": bool, "day_open": float}] | 09:30 时每只候选/持仓股票的当前数据 |

### 调仓计划

| 字段 | 类型 | 说明 |
|---|---|---|
| `sell_plan_0930` | list[{"code": str, "target_value": float, "reason": str}] | 卖出计划（含原因：目标为0/降低仓位/昨日涨停） |
| `buy_plan_0930` | list[{"code": str, "target_value": float}] | 买入计划 |

### 09:30 委托与成交

| 字段 | 类型 | 说明 |
|---|---|---|
| `orders_0930` | list[{"code": str, "direction": str, "target_amount": int, "target_value": float, "order_id": str}] | 委托记录 |
| `fills_0930` | list[{"code": str, "direction": str, "filled_amount": int, "filled_value": float, "price": float, "order_id": str}] | 实际成交记录 |
| `unfilled_reasons_0930` | list[{"code": str, "reason": str}] | 未成交原因（涨停买不到、跌停卖不掉、停牌、现金不足等） |

### 14:00 昨日涨停处理

| 字段 | 类型 | 说明 |
|---|---|---|
| `yesterday_hl_status_1400` | list[{"code": str, "close": float, "high_limit": float, "still_limit_up": bool}] | 14:00 时昨日涨停股的封板状态 |
| `orders_1400` | list[...] | 14:00 委托（开板减仓） |
| `fills_1400` | list[...] | 14:00 成交 |

### 收盘状态

| 字段 | 类型 | 说明 |
|---|---|---|
| `eod_positions` | list[{"code": str, "amount": int, "value": float, "price": float}] | 收盘持仓 |
| `eod_cash` | float | 收盘可用现金 |
| `eod_total_value` | float | 收盘总资产 |
| `eod_positions_value` | float | 收盘持仓总市值 |

---

## 建议的导出方式

在聚宽策略中添加日志函数，在每个 `run_daily` 时间点输出结构化的 JSON 行。例如：

```python
import json

def log_golden_line(context, data):
    record = {
        "date": str(context.current_dt.date()),
        "previous_date": str(context.previous_date),
        "days": g.days,
        "defensive": g.in_defensive_mode,
        "phase_targets": {str(k): v for k, v in g.phase_targets.items()},
        ...
    }
    with open("golden_log.jsonl", "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

在 `trade` 函数的 return 前和 `report_plan` 中各调用一次。

---

## 后续对比方法

local_quant 端输出相同结构的 `local_golden_log.jsonl`，通过 diff 工具逐行对比：

```python
# 伪代码
def compare_logs(jq_path, lq_path):
    with open(jq_path) as f:
        jq_lines = [json.loads(l) for l in f]
    with open(lq_path) as f:
        lq_lines = [json.loads(l) for l in f]
    for j, l in zip(jq_lines, lq_lines):
        for key in jq_keys:
            if j[key] != l.get(key):
                report_diff(j["date"], key, j[key], l[key])
```

初次对比以**信号对齐**为目标（选股列表、目标仓位、防御切换），**交易执行**的差异（委托数量、成交价）可接受并在后续阶段修复。
