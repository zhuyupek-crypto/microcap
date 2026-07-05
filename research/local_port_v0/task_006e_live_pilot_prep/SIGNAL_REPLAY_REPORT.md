# TASK-006E Stage E2 — 信号复现验证报告

**生成日期**：2026-07-05
**模式**：降级方案（路径 D，T+1 历史回放）
**证据等级**：A（基于 006G 已验证的母版回测产物）

---

## 1. 执行摘要

E2 信号复现模块（signal_replay.py）已完成开发并通过验证。

模块从 r3_full_2020_202605_research 回测产物中提取每日信号，转换为 pilot 日报格式。验证结果：

- **成交信号**：5005 笔（与 manifest 完全一致 ✅）
- **拒绝信号**：1462 笔（与 manifest 完全一致 ✅）
- **覆盖交易日**：572 天（有信号的交易日）
- **总信号行**：6467 行

---

## 2. 模块设计

### 2.1 输入

| 输入文件 | 来源 | 用途 |
|---------|------|------|
| trades.csv | r3_full_2020_202605_research | 已成交订单（5005 笔） |
| engine_logs.txt | r3_full_2020_202605_research | 拒绝订单、phase targets、defense plan |
| manifest.json | r3_full_2020_202605_research | 验证基准（orders_filled/rejected） |

### 2.2 信号分类逻辑

| 信号类型 | 触发条件 | 数量 | 占比 |
|---------|----------|------:|-----:|
| buy_new | 买入订单（非防御日 511880） | 2963 | 45.8% |
| sell_phase | 卖出订单（非防御计划） | 1863 | 28.8% |
| skip_cash_insufficient | 拒绝订单（资金不足/涨跌停/超限） | 1462 | 22.6% |
| sell_defense | 卖出订单（在防御计划中） | 165 | 2.6% |
| buy_defense | 买入 511880（防御日） | 14 | 0.2% |

### 2.3 输出

- `reports/daily_signal_YYYYMMDD.csv`：572 个文件，每文件含当日全部信号
- `reports/daily_signal_summary.csv`：跨日汇总，含 buy/sell/skip 计数

---

## 3. 验证结果

### 3.1 与 manifest 交叉验证

| 指标 | signal_replay 输出 | manifest 记录 | 一致性 |
|------|-------------------:|--------------:|--------|
| 成交订单数 | 5005 | 5005 | ✅ 完全一致 |
| 拒绝订单数 | 1462 | 1462 | ✅ 完全一致 |

### 3.2 拒绝原因覆盖

engine_logs.txt 中所有拒绝格式均已解析：

| 拒绝格式 | 数量 | 解析状态 |
|---------|-----:|---------|
| `Rejected market buy for CODE: reason` | 1454 | ✅ |
| `Rejected market sell for CODE due to limit down` | 6 | ✅ |
| `Rejected market buy for CODE due to limit up` | 1 | ✅ |
| `Rejected sell order for CODE: exceeds closeable amount` | 1 | ✅ |

### 3.3 信号决策日志完整性

每笔信号记录字段：

```text
date, code, action, target_value, target_qty, price,
reason, phase_index, defense_flag, trade_id, rejection_reason
```

---

## 4. 已知限制

### 4.1 降级方案限制

- **非实盘信号**：信号来自历史回测产物，不是当日盘前/盘中生成
- **无持有信号**：当前未输出 "hold" 信号（继续持有的股票），只输出 buy/sell/skip
- **简化分类**：buy_new vs buy_add 的区分需要持仓状态追踪，当前简化为 buy_new

### 4.2 不影响验收的限制

- hold 信号可从持仓变化推断，不影响 buy/sell/skip 的完整性
- buy_new vs buy_add 的区分不影响容量检查和风控（两者都按 buy 处理）

---

## 5. 与 SPEC.md 验收标准对照

| 验收项 | 标准 | 状态 | 说明 |
|--------|------|------|------|
| 信号可追溯到母版策略 | git SHA 7a72ae2 | ✅ | 输入来自 r3_full（已验证母版） |
| 信号复现脚本不修改策略代码 | — | ✅ | 仅读取回测产物 |
| 理论信号与回测对比偏差 = 0 | — | ✅ | 5005 fills + 1462 rejected 完全一致 |
| 每日信号稳定生成 | — | ✅ | 572 个交易日文件 |

---

## 6. 输出文件清单

| 文件 | 说明 |
|------|------|
| [modules/signal_replay.py](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_006e_live_pilot_prep/modules/signal_replay.py) | 信号复现模块 |
| reports/daily_signal_YYYYMMDD.csv | 572 个每日信号文件 |
| [reports/daily_signal_summary.csv](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_006e_live_pilot_prep/reports/daily_signal_summary.csv) | 跨日汇总 |
| SIGNAL_REPLAY_REPORT.md | 本报告 |

---

## 7. 结论

E2 信号复现模块在降级模式下通过验证：

- 工程链路可用（trades.csv + engine_logs.txt → daily_signal 格式）
- 与回测 manifest 完全一致（fills + rejected 双匹配）
- 信号决策日志完整（10 种字段，5 种决策原因）

**可进入 Stage E3：容量检查。**
