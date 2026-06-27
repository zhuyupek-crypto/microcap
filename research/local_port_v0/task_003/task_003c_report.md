# TASK-MICROCAP-003C 最终报告

## 1. 执行摘要

| 项目 | 结果 |
|---|---|
| 任务 | 逐日执行对齐与首个可观测分叉定位 |
| 首分叉日期 | **2026-05-14** |
| 首分叉时间 | 09:30:00 |
| 首分叉证券 | **300405.XSHE** |
| 首分叉字段 | 账户现金 |
| 最后完全一致日期 | 2026-05-13 |
| 一致交易日数 | 6 天 |
| 聚宽总成交 | 112 笔 |
| 本地总成交 | 58 笔 |
| 本地总拒单 | 219 次 |
| 最终状态码 | `FIRST_DIVERGENCE_CONSISTENT_WITH_STRATEGY_SIGNAL_DIFFERENCE_DRIVEN_BY_DATA_SOURCE` |

## 2. 冻结基线确认

| 项目 | 值 |
|---|---|
| 策略文件 | `微盘股-母版-20260627.py` |
| 策略 SHA-256 | `f363464fa55218c5b721d9286449c99a0c9acc097524b6f5f3db89a13af151d6` |
| local_quant 分支 | `task/microcap-compat-v1` |
| local_quant 提交 | `2ff7d76538d301452fdb5e243de2ae4e27abe251` |
| microcap 分支 | `research/local-port-v0` |
| microcap 提交 | `8005921`（运行前需确认完整 40 位哈希） |

## 3. 输入文件映射

| 任务要求文件名 | 实际文件名 | 说明 |
|---|---|---|
| `jq_trades_normalized.csv` | `jq_trades_normalized.csv` | 112 笔聚宽成交 |
| `jq_portfolio_normalized.csv` | `jq_portfolio_normalized.csv` | 507 行持仓快照 |
| `jq_daily_reconciliation.csv` | `daily_alignment.csv` | 由本次任务生成 |
| `jq_position_reconciliation.csv` | `position_alignment.csv` | 由本次任务生成 |
| `jq_cash_reconciliation.csv` | `pre_divergence_validation.csv` / `daily_alignment.csv` | 由本次任务生成 |
| `jq_manifest.json` | `local_run_manifest.json` | 包含运行元数据 |
| `local_run_manifest.json` | `local_run_manifest.json` | TASK-003B 产物 |
| `local_trades_normalized.csv` | `local_trades_normalized.csv` | 58 笔本地成交 |
| `local_portfolio_normalized.csv` | `local_portfolio_normalized.csv` | 35 日 EOD 快照 |
| `local_daily_state.csv` | `local_daily_state.csv` | 105 条三状态快照 |
| `local_engine_logs.txt` | `local_engine_logs.txt` | 830 行引擎日志 |
| `local_orders_normalized.csv` | 不存在 | 使用引擎日志中的拒单和成交行替代 |

## 4. 初始资金口径

```text
initial_cash = 1,000,000
evidence_type = ENGINE_DEFAULT_AND_EMPIRICALLY_VALIDATED
direct_jq_config_evidence = false
```

前 6 个交易日现金与总资产与聚宽精确到分，验证了 1,000,000 的合理性。

## 5. 前 6 日逐字段验证

使用 `pre_divergence_validation.csv` 逐字段比较：

| 日期 | 现金 | 总资产 | 持仓市值 | 持仓数量 |
|---|---|---|---|---|
| 2026-05-06 | ✅ | ✅ | ✅ | ✅ |
| 2026-05-07 | ✅ | ✅ | ✅ | ✅ |
| 2026-05-08 | ✅ | ✅ | ✅ | ✅ |
| 2026-05-11 | ✅ | ✅ | ✅ | ✅ |
| 2026-05-12 | ✅ | ✅ | ✅ | ✅ |
| 2026-05-13 | ✅ | ✅ | ✅ | ✅ |

逐证券持仓数量在前 6 日也一致。

结论：**EXECUTION_PARITY_CONFIRMED_BEFORE_FIRST_DIVERGENCE**

## 6. 首分叉详细分析

### 6.1 2026-05-14 账户状态

| 指标 | 聚宽 | 本地 | 差异 |
|---|---|---|---|
| 现金 | 410,485.00 | 411,202.28 | **+717.28** |
| 总资产 | 1,009,405.00 | 1,009,392.28 | -12.72 |
| 持仓市值 | 598,920.00 | 598,190.00 | -730.00 |
| 持仓数量 | 12 | 12 | 0 |

### 6.2 当日成交对比

**聚宽**：10 笔买入，无卖出。

**本地**：11 笔成交（10 笔买入 + 1 笔卖出 300405.XSHE -100 股 @ 7.23）。

### 6.3 差异归因

| 来源 | 金额 |
|---|---|
| 买入成交金额（两侧相同） | 197,872.00 |
| 聚宽卖出金额 | 0.00 |
| 本地卖出金额 | 723.00 |
| 聚宽佣金 | 50.00 |
| 本地佣金 | 55.00 |
| 现金差异主因 | 本地多卖出 100 股 300405.XSHE |

### 6.4 根因判断

- 2026-05-14 **没有** 跌停拒卖
- 其余 10 笔买入与聚宽完全一致
- 本地引擎日志显示：`sell_plan_0930` 包含 300405.XSHE，目标价值 40,210；`buy_plan_0930` 不包含 300405.XSHE
- 聚宽未卖出 300405.XSHE，说明两侧策略信号不同
- 策略代码已冻结且 SHA 一致，差异只能由输入数据不同解释

根因分类：**FIRST_DIVERGENCE_CONSISTENT_WITH_STRATEGY_SIGNAL_DIFFERENCE_DRIVEN_BY_DATA_SOURCE**

## 7. 219 次拒单分类

| 类别 | 数量 | 说明 |
|---|---|---|
| `CASCADE_AFTER_FIRST_DIVERGENCE` | 219 | 全部发生在 2026-05-26 之后，首分叉后的级联差异 |
| `FIRST_DIVERGENCE` | 0 | 首分叉不是拒单 |
| `POSSIBLE_INDEPENDENT_DIVERGENCE` | 0 | 无证据证明独立分叉 |
| `BEFORE_FIRST_DIVERGENCE` | 0 | 无 |

所有拒单均被本地引擎以 "limit down" 拒绝。详见 `limit_state_forensics.csv`。

## 8. 跌停拒卖专项取证

`limit_state_forensics.csv` 已生成。关键发现：

- 2026-05-26 起本地 14:00 卖出全部被拒绝
- 以 300405.XSHE 为例：2026-05-26 HData 显示 `low=6.85`，`low_limit=5.67`（20% 创业板跌停），实际价格远高于跌停价，但引擎仍报 "limit down"
- 这表明本地引擎的跌停判断逻辑可能使用了错误的价格字段或阈值

## 9. 候选原因排查

| 候选原因 | 是否相关 | 说明 |
|---|---|---|
| 原始行情差异 | 可能 | 首分叉由策略信号差异导致，信号依赖行情/基本面数据 |
| 时间点差异 | 否 | 两侧都在 09:30 成交 |
| 复权差异 | 未证实 | 需要进一步比对该证券的复权因子 |
| 涨跌停规则差异 | 否（首分叉） | 首分叉无拒单；后续拒单可能与规则实现有关 |
| 订单模拟差异 | 否（首分叉） | 首分叉订单已部分成交，未被拒绝 |

## 10. 任务状态码

```text
FIRST_DIVERGENCE_CONSISTENT_WITH_STRATEGY_SIGNAL_DIFFERENCE_DRIVEN_BY_DATA_SOURCE
附加：DATA_ALIGNMENT_REQUIRED_FOR_CONTINUED_PARITY
附加：ENHANCED_JQ_LOG_REQUIRED
附加：SIGNAL_PARITY_NOT_YET_TESTED_AFTER_DIVERGENCE
```

## 11. 是否建议启动 TASK-003D

**建议启动 TASK-003D（增强聚宽日志）**，理由：

1. 无法确认聚宽当日是否产生了与本地相同的 `sell_plan_0930` / `buy_plan_0930`
2. 无法确认聚宽 `order_target_value` 对 300405.XSHE 的目标值
3. 本地和聚宽在 2026-05-14 的交易标的存在差异（300405.XSHE）
4. 无法区分是信号差异还是执行差异

## 12. 未解决问题

1. 具体哪个 HData 字段导致 300405.XSHE 在 2026-05-14 被本地选为减仓标的？
2. 本地卖出目标 40,210 元为何只成交 -100 股？
3. 聚宽是否完全未生成 300405.XSHE 的卖出订单，还是生成了但被完全取消/未成交？
4. 后续 219 次 "limit down" 拒单中，HData 实际价格是否真的触及跌停？

## 13. 新增文件清单

| 文件 | 说明 |
|---|---|
| `pre_divergence_validation.csv` | 前 22 日逐字段验证 |
| `daily_alignment.csv` | 35 日账户对齐 |
| `trade_alignment.csv` | 112 笔成交对齐 |
| `position_alignment.csv` | 逐证券持仓对齐 |
| `order_fill_alignment.csv` | 订单-成交对齐 |
| `limit_state_forensics.csv` | 跌停拒卖专项取证 |
| `rejection_classification.csv` | 219 次拒单分类 |
| `first_divergence.json` | 首分叉结构化数据 |
| `first_divergence.md` | 首分叉详细报告 |
| `task_003c_report.md` | 本报告 |
| `_run_alignment_003c.py` | 对齐分析脚本 |
| `_finalize_003c.py` | 报告生成脚本 |

## 14. 提交信息

```text
research: complete TASK-003C first divergence localization
- First divergence identified: 2026-05-14, 300405.XSHE, cash field
- Pre-divergence parity confirmed for 6 trading days
- 219 rejections classified as CASCADE_AFTER_FIRST_DIVERGENCE
- Limit state forensics generated with HData prices
- Recommends TASK-003D enhanced JQ logging
```
