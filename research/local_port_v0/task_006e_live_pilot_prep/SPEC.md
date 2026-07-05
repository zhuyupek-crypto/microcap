# TASK-006E：实盘观察期与 Pilot 启动准备规格书

**版本**：v1.0
**创建日期**：2026-07-05
**前置任务**：TASK-006C（已关闭）、TASK-006D（已关闭）、TASK-006G（已关闭）
**本任务性质**：工程化准备任务，**不是研究任务**，**不以收益为验收标准**

---

## 一、任务定位

TASK-006E 不再追求历史归因或策略优化。它要回答的唯一问题是：

> 这套母版策略在真实盘中数据和真实容量约束下，能不能稳定地产生可执行订单？

只有这个问题回答"能"，才进入 50 万小资金 pilot。

### 1.1 两层架构

006E 严格分两层，**第一阶段绝不自动下单**：

| 层级 | 名称 | 周期 | 是否下单 | 资金 | 目标 |
|------|------|------|----------|------|------|
| 第一层 | 观察盘 | ≥20 个交易日 | **否**（仅生成理论信号 + 人工确认清单） | 0 | 验证数据接入、信号复现、容量检查、风控停机的工程可用性 |
| 第二层 | 小资金 Pilot | 满足进入条件后启动 | 是（人工确认 / 半自动） | 50 万 | 保守版方案落地（沿用 006D） |

### 1.2 与 006D 的关系

006D 已给出三档方案、风控规则、停机条件、恢复条件、实盘前检查清单（见 [live_pilot_plan.md](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_005_optimize/live_pilot_plan.md)）。006E **不重新设计**这些，而是把它们**工程化落地**：

- 006D 的"实盘前检查清单"（7 项 checkbox）→ 006E 的自动化验证脚本
- 006D 的"停机条件"（6 条规则）→ 006E 的风控引擎代码
- 006D 的"观察期 20 天"→ 006E 的日报框架
- 006D 的"竞价参与率 5%"→ 006E 的容量检查模块

---

## 二、工作目录

```
research/local_port_v0/task_006e_live_pilot_prep/
├── SPEC.md                           # 本规格书
├── modules/                          # 工程化模块
│   ├── data_source_adapter.py        # 实盘数据源适配器
│   ├── signal_replay.py              # 信号复现
│   ├── capacity_checker.py           # 容量与可执行性检查
│   ├── risk_engine.py                # 风控停机引擎
│   └── daily_reporter.py             # 每日报告生成
├── reports/                          # 观察期日报输出
│   ├── daily_signal_YYYYMMDD.csv
│   ├── daily_execution_feasibility_YYYYMMDD.csv
│   ├── daily_pilot_report_YYYYMMDD.md
│   └── pilot_dashboard.csv
├── config/
│   └── pilot_config.yaml             # 保守版参数（沿用 006D）
└── TASK_006E_REPORT.md               # 最终报告
```

---

## 三、五大模块

### 3.1 模块一：实盘数据源接入（data_source_adapter.py）

#### 3.1.1 目标

确认实盘所需数据字段是否可得，且与回测中使用的字段**一一对应**。核心不是"能不能拿到数据"，而是**字段语义对齐**。

#### 3.1.2 必须覆盖的字段

| 字段类别 | 字段名 | 用途 | 回测来源 | 实盘来源（待确认） | 对齐状态 |
|---------|--------|------|----------|-------------------|----------|
| 竞价 | 09:25 竞价价 | 开盘信号 | call_auction | ? | 待确认 |
| 竞价 | 09:25 竞价成交量 | 容量约束 | call_auction | ? | 待确认 |
| 涨跌停 | high_limit / low_limit | 拒单逻辑 | HData 日线 | ? | 待确认 |
| 停牌 | paused | 拒单逻辑 | HData | ? | 待确认 |
| ST | is_st | 选股过滤 | JQ 财务数据 | ? | 待确认 |
| 分钟 | 14:00 close | 减仓信号 | HData 分钟 | ? | 待确认 |
| 分钟 | 09:30 close/volume | 开盘成交 | HData 分钟 | ? | 待确认 |
| 日线 | pre_close / open / close | 信号计算 | HData 日线 | ? | 待确认 |
| 基本面 | market_cap | 选股排序 | HData | ? | 待确认 |
| 持仓 | 当前持仓 / 现金 | 风控计算 | 引擎内部 | ? | 待确认 |

#### 3.1.3 输出

```
DATA_SOURCE_FIELD_MAPPING.csv
DATA_SOURCE_FIELD_MAPPING.md
```

字段：field_name, usage, backtest_source, live_source, alignment_status, gap_description, resolution_plan

#### 3.1.4 验收

- 所有字段必须明确标注 alignment_status（aligned / partial / missing / not_applicable）
- 缺失字段必须给出 resolution_plan（替代数据源 / 降级处理 / 阻塞项）
- **严禁**在字段未对齐前进入第二层 pilot

---

### 3.2 模块二：信号复现（signal_replay.py）

#### 3.2.1 目标

每个交易日盘前/盘中生成理论信号，并记录信号产生的**完整因果链**。

#### 3.2.2 每日必须输出

```text
理论目标持仓（target_portfolio）
理论买入清单（buy_list）
理论卖出清单（sell_list）
理论目标金额（target_value_per_stock）
当前实际持仓（actual_portfolio）
差异调整金额（delta_value_per_stock）
```

#### 3.2.3 信号决策日志

每笔信号必须记录决策原因，取值之一：

```text
- buy_new           新建仓（选股命中 + 资金到位）
- buy_add           加仓（已有持仓 + phase 轮动）
- sell_phase        phase 轮动退出
- sell_defense      防御月份触发
- sell_limit_up_14h 14:00 涨停开板减仓
- sell_limit_down   跌停延迟卖出（次日补）
- sell_capacity     容量约束放弃
- sell_risk         风控停机强制清仓
- hold              继续持有
- skip              选股命中但放弃（资金/容量/涨跌停/ST）
```

#### 3.2.4 输出

```
daily_signal_YYYYMMDD.csv
daily_signal_YYYYMMDD.md  (人类可读决策日志)
```

字段：date, code, action, target_value, target_qty, reason, phase_index, defense_flag, capacity_flag

#### 3.2.5 验收

- 信号必须可追溯到 006G 已验证的母版策略（git SHA 7a72ae2）
- 信号复现脚本不得修改策略代码
- 理论信号与回测同日信号对比偏差 = 0（用 006G 的 2025/2026 对齐结果交叉验证）

---

### 3.3 模块三：容量与可执行性检查（capacity_checker.py）

**这是 006E 最核心模块**。比收益预测更重要。

#### 3.3.1 目标

每个候选订单必须输出参与率评估，并明确是否可执行。

#### 3.3.2 每笔订单必须输出

| 字段 | 说明 |
|------|------|
| code | 股票代码 |
| side | buy / sell |
| target_value | 目标金额 |
| target_qty | 目标股数 |
| auction_volume_0925 | 09:25 竞价成交量 |
| auction_value_0925 | 09:25 竞价成交额 |
| participation_rate | target_qty / auction_volume_0925 |
| is_limit_up | 是否涨停 |
| is_limit_down | 是否跌停 |
| is_paused | 是否停牌 |
| is_st | 是否 ST |
| threshold_5pct | participation_rate > 5% ? |
| threshold_10pct | participation_rate > 10% ? |
| threshold_20pct | participation_rate > 20% ? |
| executable | 是否可执行 |
| rejection_reason | 放弃原因（若不可执行） |

#### 3.3.3 阈值（沿用 006D 保守版）

```text
- 竞价参与率 > 5%：放弃（保守版）
- 竞价成交量 < 100 手：放弃
- 涨停：买入放弃，卖出延迟
- 跌停：卖出延迟到次日
- 停牌：放弃
- ST：选股阶段已过滤，若盘中变 ST 则放弃
```

#### 3.3.4 输出

```
daily_execution_feasibility_YYYYMMDD.csv
```

#### 3.3.5 验收

- 每笔候选订单都有 participation_rate 评估
- 放弃的订单必须给出 rejection_reason
- **不得**在没有容量检查的情况下提交订单

---

### 3.4 模块四：风控停机引擎（risk_engine.py）

#### 3.4.1 目标

把 006D 的停机规则从纸面落到代码。引擎必须每日自动输出风控状态。

#### 3.4.2 警戒/停机阈值（综合 006D + 用户补充）

| 指标 | 警戒阈值 | 停机阈值 |
|------|----------|----------|
| 20 日滚动收益 | < 0% | < -5% |
| 20 日滚动胜率 | < 50% | < 35% |
| 20 日最大回撤 | < -8% | < -12% |
| 连续亏损天数 | ≥ 3 | ≥ 5 |
| 订单拒绝率 | > 25% | > 40% |
| 累计回撤（相对初始资金） | > -10% | > -15% |

#### 3.4.3 风控状态机

```text
状态：NORMAL / WARNING / HALTED / RECOVERY
转换：
  NORMAL  → WARNING  任一警戒阈值触发
  WARNING → NORMAL   所有警戒阈值恢复（连续 3 日）
  WARNING → HALTED   任一停机阈值触发
  HALTED  → RECOVERY 人工确认后进入恢复观察
  RECOVERY → NORMAL  连续 20 个交易日所有指标正常
  RECOVERY → HALTED  任一停机阈值再次触发
```

#### 3.4.4 仓位缩放规则（沿用 006D）

- 累计回撤 > -10%：仓位降至 50%
- 累计回撤修复到 < -5%：仓位恢复 80%
- 当月亏损 > -8%：本月剩余时间仓位降至 50%

#### 3.4.5 输出

```
daily_risk_status_YYYYMMDD.csv
daily_risk_status_YYYYMMDD.md
```

字段：date, indicator, value, threshold, status, action

#### 3.4.6 验收

- 风控引擎必须能在历史数据上回放验证（用 006D 的 risk_control_scenarios 交叉验证）
- 任一停机阈值触发必须立即输出 HALTED 状态
- **严禁**在 HALTED 状态下提交订单

---

### 3.5 模块五：每日 Pilot 报告（daily_reporter.py）

#### 3.5.1 目标

每天输出一份可直接用于盘前/盘中决策的报告。

#### 3.5.2 日报必须回答

```text
1. 今天有没有信号？
2. 理论上应该买卖什么？
3. 实盘是否可执行？
4. 哪些票因为容量/涨跌停/停牌放弃？
5. 今天是否触发警戒？
6. 今天是否触发停机？
7. 是否允许明天继续观察？
```

#### 3.5.3 输出文件

```
daily_signal_YYYYMMDD.csv                 (信号复现)
daily_execution_feasibility_YYYYMMDD.csv  (容量检查)
daily_risk_status_YYYYMMDD.csv            (风控状态)
daily_pilot_report_YYYYMMDD.md            (人类可读日报)
pilot_dashboard.csv                       (汇总看板，逐日追加)
```

#### 3.5.4 pilot_dashboard.csv 字段

```text
date, signals_count, executable_count, rejected_count,
risk_status, position_scale, cumulative_return, drawdown,
consecutive_losses, rolling_20d_winrate, rolling_20d_return,
action_tomorrow (continue / warn / halt)
```

#### 3.5.5 验收

- 连续 20 个交易日都有完整日报
- 日报可被非技术人员理解
- dashboard 可用于快速判断是否继续观察

---

## 四、进入第二层 Pilot 的条件

**所有条件必须同时满足**，缺一不可：

1. 第一层观察盘连续运行 ≥ 20 个交易日
2. 数据源字段对齐全部 aligned（无 missing）
3. 信号复现与回测同日对比偏差 = 0
4. 容量检查模块稳定运行，无崩溃
5. 风控引擎在历史数据回放验证通过
6. 2026 退化判断：20 日滚动胜率 > 50%（沿用 006D 检查清单）
7. 人工审核确认市场环境未发生结构性变化
8. 资金 50 万已到位
9. 券商接口支持竞价限价单
10. 首日仅下一笔测试单，确认全链路通畅

---

## 五、保守版参数（pilot_config.yaml）

沿用 006D 保守版，不重新设计：

```yaml
initial_cash: 500000
position_scale: 0.8
max_single_position_pct: 0.05
max_holding_count: 30
max_daily_turnover_pct: 0.30
max_daily_loss_pct: -0.03
max_monthly_loss_pct: -0.08
max_drawdown_halt: -0.15
consecutive_loss_halt: 5
observation_days: 20
auction_participation_rate_limit: 0.05
min_auction_volume_lots: 100
allow_auto_order: false
```

---

## 六、阶段划分

### Stage E1：数据源字段对齐（模块一）
- 输出 DATA_SOURCE_FIELD_MAPPING.csv/md
- 验收：所有字段对齐或明确降级方案

### Stage E2：信号复现（模块二）
- 输出 daily_signal 模板
- 验收：与回测信号对比偏差 = 0

### Stage E3：容量检查（模块三）
- 输出 daily_execution_feasibility 模板
- 验收：每笔订单有参与率评估

### Stage E4：风控引擎（模块四）
- 输出 daily_risk_status 模板
- 验收：历史回放验证通过

### Stage E5：日报框架（模块五）
- 输出 daily_pilot_report 模板 + dashboard
- 验收：日报可读性

### Stage E6：观察盘试运行（≥20 交易日）
- 连续 20 日生成完整日报
- 验收：稳定运行无崩溃

### Stage E7：进入第二层 Pilot 评估
- 输出 PILOT_READINESS_REPORT.md
- 验收：第四节 10 条进入条件全部满足

---

## 七、验收标准

006E **不以收益为验收**。验收标准：

| # | 验收项 | 标准 |
|---|--------|------|
| 1 | 数据接入 | 实盘所需字段完整且对齐 |
| 2 | 信号复现 | 每日理论信号稳定生成，与回测偏差 = 0 |
| 3 | 容量检查 | 每笔订单都有参与率评估 |
| 4 | 风控机制 | 警戒/停机状态可自动输出，历史回放验证通过 |
| 5 | 人工确认清单 | 可直接用于盘前/盘中决策 |
| 6 | 观察期报告 | 连续 20 个交易日可追踪 |
| 7 | 不自动交易 | 第一阶段只观察，不自动下单 |
| 8 | 进入条件 | 第四节 10 条进入条件明确评估 |
| 9 | 不修改策略 | 母版策略 git SHA 不变 |
| 10 | 不修改引擎 | 引擎代码不变（仅新增 pilot 模块） |

---

## 八、禁止事项

1. 禁止在第一层观察盘阶段自动下单
2. 禁止修改母版策略代码
3. 禁止修改回测引擎核心逻辑
4. 禁止跳过容量检查直接提交订单
5. 禁止在 HALTED 状态下继续交易
6. 禁止用 006E 收益结果反推优化策略参数
7. 禁止把观察盘的短期收益作为最终 pilot 决策依据
8. 禁止在数据源字段未对齐前进入第二层

---

## 九、与已有任务的关系

| 任务 | 关系 |
|------|------|
| 006C | 提供 48.33% 基线、成本敏感性、年度汇总。006E 不重做 |
| 006D | 提供保守版方案、风控规则、停机条件、容量上限。006E 工程化落地 |
| 006F-A | 证明 Research = jq_parity。006E 不再对比 |
| 006G | 证明本地 Research 是实盘基线，聚宽 68.24% 降为 C 级。006E 沿用本地 Research |
| 003 | 提供 2026 片段首分叉根因（数据源差异）。006E 数据源对齐参考 |

---

## 十、最终决策口径

006E 完成后，决策树：

```text
若 E1-E7 全部通过 + 第四节 10 条进入条件全满足
  → 进入第二层 50 万小资金 Pilot

若 E1-E7 部分未通过
  → 修复后重新试运行
  → 不得跳过未通过项

若数据源字段无法对齐
  → 阻塞，不进入 Pilot
  → 输出阻塞清单，等待数据源解决

若 2026 退化未确认结束
  → 继续观察盘
  → 不进入实盘
```

---

## 十一、默认假设

- 实盘数据源：待 E1 确认（候选：HData 实盘 / 券商 API / JQ 模拟盘）
- 券商接口：待用户确认
- 观察盘起始日期：E1-E5 完成后确定
- 观察盘期间不计实际盈亏（仅理论盈亏）

---

## 十二、不做什么

明确 006E **不做**以下事项：

- 不做策略优化
- 不做参数寻优
- 不做历史归因（006G 已闭环）
- 不做收益预测
- 不做容量上限重估（006D 已定）
- 不做风控规则重设计（006D 已定）
- 不做母版 vs 优化版对比（006F-R1 已证伪）

---

## 附录 A：006D 已有产物清单（006E 直接引用）

| 文件 | 用途 |
|------|------|
| [live_pilot_plan.md](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_005_optimize/live_pilot_plan.md) | 三档方案、风控规则、停机条件、实盘前检查清单 |
| [TASK_006D_RISK_CONTROL.md](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_005_optimize/runs/TASK_006D_RISK_CONTROL.md) | 风控场景回测结果（pos_80/max_dd -18.86%） |
| [TASK_006D_CAPACITY.md](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_005_optimize/runs/TASK_006D_CAPACITY.md) | 容量压力测试（1M 资金 30.78% fill rate） |
| [TASK_006D_COST_EQUITY.md](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_005_optimize/runs/TASK_006D_COST_EQUITY.md) | 成本后净值曲线 |
| [risk_control_scenarios.py](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_005_optimize/risk_control_scenarios.py) | 风控场景回放脚本 |
| [capacity_stress_test.py](file:///d:/Work%20Space/他山之石/微盘股/research/local_port_v0/task_005_optimize/capacity_stress_test.py) | 容量压力测试脚本 |

---

## 附录 B：006G 已确认的边界（006E 必须遵守）

1. 本地 Research 48.33% 是实盘基线
2. 聚宽 68.24% 是 C 级宏观参考，不作为实盘预期
3. 策略代码 git SHA 7a72ae2 不可修改
4. 成交模型 16 维度已对齐，006E 必须保持
5. 数据源 6 个差异已识别（分钟 close / ETF 精度 / call_auction / market_cap / ST / 停牌），006E 必须在数据源对齐中覆盖

---

**本规格书不再等待新的讨论。直接按此执行。**
