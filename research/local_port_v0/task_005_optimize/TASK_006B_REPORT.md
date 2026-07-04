# TASK-006B REPORT

TASK-006B：绩效统计口径修复与回测报告可信化
==============================================

> 本报告按用户要求只回答 6 个问题：
> 1. 修复了哪些统计口径？
> 2. 新增了哪些报告文件？
> 3. 7 个 R2 run 的核心指标汇总是什么？
> 4. 旧口径和新口径最大的差异是什么？
> 5. 是否满足 10 条验收标准？
> 6. 是否可以进入 TASK-006C？

---

## 1. 修复了哪些统计口径

| # | 口径 | 旧实现（backtest_runner.extended_metrics） | 新实现（performance_report.py） |
|---|------|--------------------------------------------|---------------------------------|
| 1.1 | **胜率** | 按 `code` 分组，比较“加权平均卖出价 > 加权平均买入价”；一个 code 算一次 | 基于 **FIFO 闭环**：每次卖出按 FIFO 拆分到具体买入 lot，每个 lot 是一笔独立 closed_trade；`win_rate = count(gross_pnl>0) / number_of_closed_trades` |
| 1.2 | **最大回撤** | 只输出 `max_drawdown` 数值 + `max_dd_duration_days`（trading-day 索引差） | 输出 `max_drawdown` + `max_drawdown_start`（日历日）+ `max_drawdown_end`（日历日） |
| 1.3 | **年化收益** | `annual_return`（公式同 CAGR，但命名模糊） | `annual_return_cagr`（明确标注 CAGR 公式 `(ending/initial)^(252/days)-1`） |
| 1.4 | **夏普** | `(annual_return - 0.03) / volatility` | `sharpe_annualized = (annual_return_cagr - 0.03) / volatility_annualized`，公式相同但口径写明 |
| 1.5 | **换手率** | 单一 `annual_turnover = turnover_value / initial_cash * (252/days)` | 拆分为 `buy_turnover` / `sell_turnover` / `gross_turnover` / `annualized_gross_turnover`，公式明确 |
| 1.6 | **闭环交易统计** | 无 | 新增 `closed_trade_metrics`：`number_of_closed_trades` / `win_rate` / `average_return` / `median_return` / `average_win` / `average_loss` / `profit_loss_ratio` / `expectancy_per_trade` / `average_holding_days` / `median_holding_days` |
| 1.7 | **未平仓统计** | `ending_positions` dict 但无汇总 | 新增 `open_position_metrics`：`number_of_open_positions` / `open_positions_value` + 说明“不计入胜率” |
| 1.8 | **执行质量** | `orders` dict（submitted/filled/rejected） | 新增 `execution_quality`：`fill_rate = filled/submitted`（submitted=0 时为 null）+ `rejection_reasons` |
| 1.9 | **空数据稳健性** | 无闭环时 `win_rate=0`，误导 | 无闭环时所有 `closed_trade_metrics` 为 `null`，并在 `notes` 说明 |
| 1.10 | **结构化输出** | 仅 manifest.json 中 `metrics` 字段 + 终端打印 | 生成 `performance_report.json`（机器可读）/ `summary.md`（人可读）/ `closed_trades.csv`（明细） |

---

## 2. 新增了哪些报告文件

### 2.1 代码文件

| 文件 | 作用 |
|------|------|
| `research/local_port_v0/task_005_optimize/performance_report.py` | 纯统计逻辑模块（FIFO 配对、指标计算、报告生成） |
| `research/local_port_v0/task_005_optimize/backtest_runner.py` | 修改：在 manifest 写入后调用 `performance_report.generate_report(output_dir)` |

### 2.2 每个 run 目录新增（7 个 run × 3 文件 = 21 文件）

| 文件 | 作用 |
|------|------|
| `performance_report.json` | 机器可读完整指标（equity/trade_flow/closed_trade/open_position/execution_quality + notes） |
| `summary.md` | 人可读摘要（5 个 section） |
| `closed_trades.csv` | FIFO 闭环明细（code/open_date/close_date/quantity/buy_price/sell_price/gross_pnl/gross_return/holding_days） |

### 2.3 汇总文件（2 个）

| 文件 | 作用 |
|------|------|
| `runs/TASK_006B_SUMMARY.csv` | 7 个 run × 25 字段，机器可读汇总 |
| `runs/TASK_006B_SUMMARY.md` | 7 个 run 的 markdown 表格 |

### 2.4 本报告

| 文件 | 作用 |
|------|------|
| `TASK_006B_REPORT.md` | 本文件 |

---

## 3. 7 个 R2 run 的核心指标汇总

数据来源：`runs/TASK_006B_SUMMARY.csv`（生成于 2026-07-04）。

| tag | mode | days | ending_value | total_return | CAGR | max_dd | dd_start | dd_end | sharpe | gross_turnover | ann_turnover | fills | closed | win_rate | avg_ret | pl_ratio | expectancy | avg_hold | submit | filled | rejected | fill_rate |
|-----|------|------|--------------|--------------|------|--------|----------|--------|--------|----------------|--------------|-------|--------|----------|---------|----------|------------|----------|--------|--------|----------|-----------|
| r2_window1_research | research | 25 | 856,452.69 | -14.90% | -80.32% | -22.69% | 2024-05-17 | 2024-06-06 | -1.83 | 147.98% | 1491.68% | 99 | 31 | 41.94% | -2.00% | 0.68 | -2.00% | 21.94 | 107 | 99 | 8 | 92.52% |
| r2_window1_jq_parity | jq_parity | 25 | 856,452.69 | -14.90% | -80.32% | -22.69% | 2024-05-17 | 2024-06-06 | -1.83 | 147.98% | 1491.68% | 99 | 31 | 41.94% | -2.00% | 0.68 | -2.00% | 21.94 | 107 | 99 | 8 | 92.52% |
| r2_window2_research | research | 39 | 1,000,507.64 | -0.80% | -5.06% | -11.62% | 2025-03-20 | 2025-03-31 | -0.30 | 218.41% | 1411.27% | 158 | 75 | 93.33% | 17.01% | 3.14 | 17.01% | 21.88 | 176 | 158 | 18 | 89.77% |
| r2_window2_jq_parity | jq_parity | 39 | 1,000,507.64 | -0.80% | -5.06% | -11.62% | 2025-03-20 | 2025-03-31 | -0.30 | 218.41% | 1411.27% | 158 | 75 | 93.33% | 17.01% | 3.14 | 17.01% | 21.88 | 176 | 158 | 18 | 89.77% |
| r2_window3_research | research | 17 | 933,795.26 | -6.73% | -64.39% | -7.49% | 2026-05-14 | 2026-05-28 | -2.98 | 115.17% | 1707.28% | 63 | 6 | 50.00% | 5.00% | 5.14 | 5.00% | 18.83 | 63 | 63 | 0 | 100.00% |
| r2_window3_jq_parity | jq_parity | 17 | 933,795.26 | -6.73% | -64.39% | -7.49% | 2026-05-14 | 2026-05-28 | -2.98 | 115.17% | 1707.28% | 63 | 6 | 50.00% | 5.00% | 5.14 | 5.00% | 18.83 | 63 | 63 | 0 | 100.00% |
| r2_missing_202606_research | research | 19 | 928,977.00 | -7.77% | -65.81% | -7.78% | 2026-06-01 | 2026-06-24 | -3.10 | 81.20% | 1076.98% | 53 | 0 | null | null | null | null | null | 87 | 53 | 34 | 60.92% |

**关键观察**：

- **Research / jq_parity 数值完全一致**：3 个正式窗口的 research 与 jq_parity 在所有指标上完全相同，证明 R2 因果修复未改变成交结果（仅在 fail-closed 路径有差异）。
- **r2_missing_202606_research 无闭环**：53 笔全部为买入（53 buy / 0 sell），FIFO 无法配对，`number_of_closed_trades=0`，所有 `closed_trade_metrics` 为 `null`（不是 0），符合验收标准 7。
- **胜率差异显著**：window1 41.94% / window2 93.33% / window3 50.00%，反映不同市场环境下的策略表现差异。

---

## 4. 旧口径和新口径最大的差异

### 4.1 胜率口径差异（最大）

| run | 旧 win_rate（按 code 平均价） | 新 win_rate（FIFO 闭环） | 差异 |
|-----|------------------------------|--------------------------|------|
| r2_window1_research | 45.83% | 41.94% | **-3.89pp** |
| r2_window2_research | 87.72% | 93.33% | **+5.61pp** |
| r2_window3_research | 40.00% | 50.00% | **+10.00pp** |
| r2_missing_202606_research | 0.00% | **null** | **修正：旧口径误导为 0%** |

**原因**：
- 旧口径按 `code` 分组，比较“加权平均卖出价 > 加权平均买入价”。一个 code 无论分几次卖出都只算一次决策。
- 新口径按 FIFO 拆分，每次卖出匹配到具体买入 lot，一个 lot 是一笔独立闭环。同一 code 多次买入 + 一次卖出会产生多笔闭环。
- 差异方向不固定：window1 新口径更低（FIFO 暴露了后期高价 lot 的亏损），window2/3 新口径更高（FIFO 暴露了低价 lot 的盈利）。
- **r2_missing_202606_research 旧口径给 0% 是错的**——该 run 没有任何卖出，根本不应该有胜率。新口径正确返回 `null`。

### 4.2 最大回撤区间（次大）

| run | 旧 max_dd_duration_days | 新 max_drawdown_start | 新 max_drawdown_end | 新区间日历日数 |
|-----|-------------------------|-----------------------|---------------------|----------------|
| r2_window1_research | 14（trading days） | 2024-05-17 | 2024-06-06 | 20 calendar days |
| r2_window2_research | 7（trading days） | 2025-03-20 | 2025-03-31 | 11 calendar days |
| r2_window3_research | 10（trading days） | 2026-05-14 | 2026-05-28 | 14 calendar days |

**原因**：旧口径只给 trading-day 索引差，无法定位具体日期；新口径给出实际日历日期，便于与外部事件对照。

### 4.3 其他差异

- **年化收益**：数值相同，仅命名从 `annual_return` 改为 `annual_return_cagr`（明确 CAGR 公式）。
- **换手率**：数值相同，但新口径拆分为 buy/sell/gross 三个分量，便于诊断“买入多卖出少”的不平衡。
- **闭环交易统计**：旧口径完全没有，新口径完整输出（number/avg_return/median/pl_ratio/expectancy/holding_days）。
- **执行质量**：旧口径只有 orders dict，新口径增加 `fill_rate` 和结构化 `rejection_reasons`。

---

## 5. 是否满足 10 条验收标准

### A. 文件产物

| # | 标准 | 状态 | 证据 |
|---|------|------|------|
| 1 | 7 个 R2 run 目录中每个都有 `performance_report.json` / `summary.md` / `closed_trades.csv` | **PASS** | `runs/r2_window1_research/` 等 7 个目录各含 3 文件，共 21 文件 |
| 2 | 生成总汇总 `runs/TASK_006B_SUMMARY.md` / `runs/TASK_006B_SUMMARY.csv` | **PASS** | `runs/TASK_006B_SUMMARY.md`（7 行表格）+ `runs/TASK_006B_SUMMARY.csv`（25 字段） |

### B. 指标口径

| # | 标准 | 状态 | 证据 |
|---|------|------|------|
| 3 | `performance_report.json` 明确区分 `equity_metrics` / `trade_flow_metrics` / `closed_trade_metrics` / `open_position_metrics` / `execution_quality` | **PASS** | 见 §3 任意 `performance_report.json` 结构 |
| 4 | 胜率必须来自 `closed_trades.csv`，不得来自成交行数 | **PASS** | `closed_trade_metrics.win_rate` 由 `_build_closed_trades()` FIFO 配对后计算；`closed_trades.csv` 是同一来源的明细 |
| 5 | 最大回撤必须输出 `max_drawdown` / `max_drawdown_start` / `max_drawdown_end` | **PASS** | `equity_metrics` 三字段均有值（如 window1: -22.69% / 2024-05-17 / 2024-06-06） |
| 6 | 换手率必须输出 `gross_turnover` / `annualized_gross_turnover` | **PASS** | `trade_flow_metrics` 含 `gross_turnover` + `annualized_gross_turnover`（另附 buy/sell 分量） |

### C. 稳健性

| # | 标准 | 状态 | 证据 |
|---|------|------|------|
| 7 | 无闭环交易时闭环指标必须为 `null`，不能报错，不能硬填 0 | **PASS** | `r2_missing_202606_research` 的 `closed_trade_metrics` 全部为 `null`，`notes` 说明“No closed trades” |
| 8 | `trades.csv` 为空或缺失时报告仍能生成，交易相关指标为 `null` 或 0，并在 `notes` 说明 | **PASS** | `_trade_flow_metrics` 对 None/empty 返回 0；`_closed_trade_metrics` 对空列表返回 null；`notes` 自动追加“trades.csv missing/empty” |
| 9 | 所有报告生成逻辑只读取 `equity.csv` / `trades.csv` / `manifest.json`，不访问行情，不重跑回测 | **PASS** | `performance_report.py` 仅 import `pandas`/`csv`/`json`/`statistics`，无 `engine`/`data_api`/`HData` 依赖；`_load_*` 函数只读三个文件 |

### D. 工程边界

| # | 标准 | 状态 | 证据 |
|---|------|------|------|
| 10 | 不修改策略文件 / local_quant 引擎 / Research|jq_parity 成交逻辑 / R2 已有回归结果 | **PASS** | (a) 策略文件未改；(b) local_quant 仓库未改（仅 microcap）；(c) `backtest_runner.py` 只在 manifest 写入后追加 `generate_report()` 调用，不触及 engine 调用路径；(d) R2 的 7 个 run 的 `equity.csv`/`trades.csv`/`manifest.json` 未改（新增 3 文件不影响原文件） |

**10 条验收全部满足。**

---

## 6. 是否可以进入 TASK-006C

**可以。**

TASK-006B 已完成全部 10 条验收，所有报告文件已生成，统计口径已修复并文档化。未修改策略、引擎、成交逻辑，未扩大范围。

下一工作项 TASK-006C（Research 模式下的策略表现复核与实盘可行性判断）可以开始。

---

## 附录：交付物清单

```
research/local_port_v0/task_005_optimize/
├── performance_report.py                          # 新增：纯统计逻辑
├── backtest_runner.py                             # 修改：调用 generate_report
├── TASK_006B_REPORT.md                            # 新增：本报告
└── runs/
    ├── r2_window1_research/
    │   ├── performance_report.json                # 新增
    │   ├── summary.md                             # 新增
    │   └── closed_trades.csv                      # 新增
    ├── r2_window1_jq_parity/                      # 同上 3 文件
    ├── r2_window2_research/                       # 同上 3 文件
    ├── r2_window2_jq_parity/                      # 同上 3 文件
    ├── r2_window3_research/                       # 同上 3 文件
    ├── r2_window3_jq_parity/                      # 同上 3 文件
    ├── r2_missing_202606_research/                # 同上 3 文件
    ├── TASK_006B_SUMMARY.md                       # 新增：汇总
    └── TASK_006B_SUMMARY.csv                      # 新增：汇总
```

---

**TASK-006B 完成。可进入 TASK-006C。**
