"""Finalize TASK-003C reports."""
import json, os
from pathlib import Path
from datetime import datetime

ODIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003")

# Load first_divergence.json generated earlier
with open(ODIR / "first_divergence.json", "r", encoding="utf-8") as f:
    first_div = json.load(f)

# Correct/update first divergence based on 2026-05-14 trade analysis
first_div.update({
    "first_divergence_date": "2026-05-14",
    "first_divergence_time": "09:30:00",
    "security": "300405.XSHE",
    "field": "cash",
    "jq_value": 410485.0,
    "local_value": 411202.28,
    "jq_current_event": "JQ had 10 buy trades on 2026-05-14, NO sell of 300405.XSHE; kept 5600 shares",
    "local_current_event": "Local executed 10 buy trades PLUS a sell of 100 shares of 300405.XSHE @ 7.23",
    "local_order_intent": "sell_plan_0930 listed 300405.XSHE target=40210 (exit/reduction), buy_plan_0930 did not include 300405.XSHE",
    "local_order_result": "PARTIAL_FILL: -100 shares of 300405.XSHE @ 7.23",
    "local_rejection_reason": "None (order executed partially at 09:30; not rejected)",
    "root_or_cascade": "ROOT",
    "evidence_level": "STRONG",
    "candidate_root_cause": "FIRST_DIVERGENCE_CONSISTENT_WITH_STRATEGY_SIGNAL_DIFFERENCE_DRIVEN_BY_DATA_SOURCE",
    "root_cause_detail": "Strategy code is identical. On 2026-05-14 local engine's sell_plan/buy_plan calculation decided to reduce/exit 300405.XSHE, while JQ kept it. This is consistent with HData fundamental/market data differing from JQ data, causing stock selection/rotation decisions to diverge. No engine rejection occurred on this date; the order was partially filled. Cannot prove JQ's internal target value because JQ logs do not expose order intent.",
    "unresolved_questions": [
        "Which exact HData fundamental or price field caused 300405.XSHE to be selected for reduction locally but kept on JQ?",
        "Why was only -100 shares filled locally when target value implied ~5562 shares?",
        "Does JQ's order_target_value fill more aggressively for the same target?"
    ]
})

# Load previous day state
first_div["jq_previous_state"] = {
    "date": "2026-05-13",
    "cash": 608407.0,
    "total_asset": 1002141.0,
    "positions_value": 393734.0,
    "position_count": 11,
    "300405.XSHE_quantity": 5600
}
first_div["local_previous_state"] = {
    "date": "2026-05-13",
    "cash": 608407.0,
    "total_asset": 1002141.0,
    "positions_value": 393734.0,
    "position_count": 11,
    "300405.XSHE_quantity": 5600
}

with open(ODIR / "first_divergence.json", "w", encoding="utf-8") as f:
    json.dump(first_div, f, indent=2, ensure_ascii=False, default=str)

print("Updated first_divergence.json")

# Write first_divergence.md
md = """# TASK-MICROCAP-003C：首个可观测分叉定位报告

## 1. 首分叉概览

| 字段 | 值 |
|---|---|
| 首个分叉日期 | 2026-05-14 |
| 分叉时间 | 09:30:00 |
| 分叉证券 | **300405.XSHE** |
| 分叉字段 | 账户现金 (cash) |
| 聚宽现金 | 410,485.00 |
| 本地现金 | 411,202.28 |
| 现金差异 | **+717.28** |
| 总资产差异 | -12.72 |
| 持仓市值差异 | -730.00 |
| 最后一致日期 | 2026-05-13 |
| 证据等级 | STRONG |
| 根因分类 | `FIRST_DIVERGENCE_CONSISTENT_WITH_STRATEGY_SIGNAL_DIFFERENCE_DRIVEN_BY_DATA_SOURCE` |

## 2. 分叉前最后一个共同状态（2026-05-13）

| 指标 | 聚宽 | 本地 |
|---|---|---|
| 现金 | 608,407.00 | 608,407.00 |
| 总资产 | 1,002,141.00 | 1,002,141.00 |
| 持仓市值 | 393,734.00 | 393,734.00 |
| 持仓数量 | 11 | 11 |
| 300405.XSHE 持仓 | 5,600 股 | 5,600 股 |

✅ 分叉前最后一个交易日，账户与持仓完全一致。

## 3. 2026-05-14 两侧行为对比

### 聚宽（JQ）

- 当日成交 10 笔，全部为买入
- **没有卖出 300405.XSHE**
- 2026-05-14 日终 300405.XSHE 持仓仍为 **5,600 股**
- 现金减少：608,407 - 410,485 = **197,922**（买入成本 + 佣金）

### 本地（local_quant）

- 当日成交 11 笔：10 笔买入 + 1 笔卖出
- **卖出 300405.XSHE -100 股 @ 7.23**（部分成交）
- 2026-05-14 日终 300405.XSHE 持仓变为 **5,500 股**
- 现金变化：608,407 - 197,872（买） - 55（佣金） + 723（卖）= **411,203 ≈ 411,202.28**

### 差异来源

| 项目 | 聚宽 | 本地 | 差异 |
|---|---|---|---|
| 买入成交金额 | 197,872.00 | 197,872.00 | 0.00 |
| 卖出成交金额 | 0.00 | 723.00 | +723.00 |
| 佣金 | 50.00 | 55.00 | +5.00 |
| 净现金变化 | -197,922.00 | -197,204.00 | **+718.00** |

> 注意：717.28 与 718.00 的微小差异来自持仓市值波动与四舍五入。核心差异就是本地多卖出 100 股 300405.XSHE。

## 4. 根因分析

### 4.1 不是执行模型问题

- 2026-05-14 **没有** 任何跌停拒卖日志
- 本地卖出订单被**部分成交**（-100 股），未被拒绝
- 其余 10 笔买入与聚宽价格、数量完全一致

### 4.2 不是行情字段差异导致的拒单

- limit_state_forensics.csv 中 2026-05-14 没有任何拒单记录
- 第一个拒单发生在 2026-05-26，晚于首分叉 12 个交易日
- 因此首分叉与后续 219 次拒单无关

### 4.3 是策略信号差异

- 本地引擎日志显示：`sell_plan_0930` 包含 300405.XSHE（目标价值 40,210），`buy_plan_0930` 不包含 300405.XSHE
- 这说明本地策略在 2026-05-14 决定**减仓/退出 300405.XSHE**
- 聚宽未产生对应卖出，说明聚宽策略在该日**继续持有 300405.XSHE**
- 策略代码已冻结且 SHA 一致，差异只能来自**输入数据不同**（HData vs 聚宽行情/财务数据）

### 4.4 证据限制

- 无法直接获取聚宽策略当日的 `sell_plan_0930` / `buy_plan_0930` 内部值
- 无法确定具体是哪一个 HData 字段（基本面、前复权、成交量、ST 状态等）导致信号分歧
- 因此不能写 `FIRST_DIVERGENCE_CAUSED_BY_LOCAL_MARKET_DATA`，只能写：`FIRST_DIVERGENCE_CONSISTENT_WITH_STRATEGY_SIGNAL_DIFFERENCE_DRIVEN_BY_DATA_SOURCE`

## 5. 级联影响

- 2026-05-14 之后，本地持仓与聚宽持仓开始偏离
- 2026-05-26 起，本地 14:00 卖出全部被引擎以 "limit down" 拒绝（共 219 次），属于首分叉后的级联差异
- 由于持仓已经不同，后续拒单全部标记为 `CASCADE_AFTER_FIRST_DIVERGENCE`

## 6. 未解决问题

1. 具体是 HData 哪个字段导致 300405.XSHE 在 2026-05-14 被本地选为减仓标的？
2. 本地卖出目标为 40,210 元（约 5,562 股），为何只成交 -100 股？是否受聚宽 `order_target_value` 与本地实现差异影响？
3. 聚宽当日未卖出，是否因为聚宽的 `sell_plan_0930` 未包含 300405.XSHE，还是聚宽的订单被完全撮合为 0？

## 7. 结论与状态码

- 前 6 个交易日（2026-05-06 至 2026-05-13）：**EXECUTION_PARITY_CONFIRMED_BEFORE_FIRST_DIVERGENCE**
- 首分叉日期：**2026-05-14**
- 首分叉证券：**300405.XSHE**
- 根因分类：**FIRST_DIVERGENCE_CONSISTENT_WITH_STRATEGY_SIGNAL_DIFFERENCE_DRIVEN_BY_DATA_SOURCE**
- 后续 219 次拒单：**CASCADE_AFTER_FIRST_DIVERGENCE**
- 是否建议 TASK-003D：**YES** — 需要增强聚宽日志以捕获策略内部 `sell_plan_0930` / `buy_plan_0930` 和 `order_target_value` 的订单意图，否则无法区分信号差异与执行差异
"""

with open(ODIR / "first_divergence.md", "w", encoding="utf-8") as f:
    f.write(md)

print("Wrote first_divergence.md")
