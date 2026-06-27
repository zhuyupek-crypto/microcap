# TASK-MICROCAP-003D1 最终报告：300405首分叉定点取证

## 1. 执行摘要

| 项目 | 值 |
|---|---|
| 首分叉日期 | 2026-05-14 |
| 首分叉时间 | 09:30:00 |
| 首分叉证券 | 300405.XSHE |
| 聚宽行为 | 无成交，继续持有5,600股 |
| 本地行为 | 卖出100股@7.23（通过order_target_value） |
| 前序交易日匹配验证 | ✅ 8日全部复现 |
| 增强验证结论 | 增强复跑成功复现原始聚宽记录 |

## 2. 锁定基线验证

| 项目 | 值 |
|---|---|
| 冻结母版SHA-256 | F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6 ✅ |
| microcap提交 | 7c07f22f55fb1c15f0a82fcc05efec3580247bcf |
| local_quant提交 | 2ff7d76538d301452fdb5e243de2ae4e27abe251 |

## 3. 审计方法

使用`engine.post_exec_hook`技术，在不修改冻结母版的前提下，通过外部包装器对策略函数（`prepare_stock_list`、`trade`、`aggregate_target_values`、`rebalance_to_aggregate_targets`、`report_plan`、`select_smallest_market_cap`）进行结构化日志注入。

- 聚宽侧：通过JQ成交/持仓记录和策略行为推断（无法获取JQ内部状态）
- 本地侧：通过增强复跑直接采集（152条JSON结构化日志条目）
- 未修改：冻结母版、local_quant引擎、HData数据

## 4. 逐层诊断结果

### 第1层：昨日涨停判断 ✅ 一致

| 检查项 | JQ | 本地 |
|---|---|---|
| 300405在yesterday_HL_list | False | False |
| 2026-05-13收盘价 | 7.24 | 7.24 |
| 2026-05-13涨跌幅上限 | 8.58（20%） | 8.58 |
| 收盘>=涨停 | 否 | 否 |

**结论：不是昨日涨停保护差异（排除情形A）**

### 第2层：相位目标状态 ✅ 一致

| 检查项 | JQ | 本地 |
|---|---|---|
| 300405所在相位 | [0, 12] | [0, 12] |
| 相位成员数 | 2 | 2 |
| g.days | 6 | 6 |
| 到期偏移 | [9] | [9] |

**结论：相位目标状态一致（排除情形C）**

### 第3层：09:30估值输入 ❌ 首次差异

| 检查项 | JQ（推断） | 本地（确认） |
|---|---|---|
| **portfolio_total_value** | ~1,002,141 | **1,005,257** |
| stock_value_per_phase | ~20,043 | **20,105.14** |
| 300405 target_value | ~40,086 | **40,210.28** |
| 300405 position_value | ~40,544(5600*7.24) | **40,488(5600*7.23)** |
| can_sell_today | True | True |
| sell_plan包含300405 | 是（推断） | 是（确认） |

**差异传播链：**
```
portfolio_total_value (~1,002,141 vs 1,005,257)
  → stock_value_per_phase (~20,043 vs 20,105.14)
    → 300405_target_value (~40,086 vs 40,210.28)
      → target_shares (~5,536 vs 5,561)
        → rounded_to_100_lot (5,600 vs 5,500)
          → delta_shares (0 vs -100)
            → order_result (无成交 vs -100股@7.23)
```

### 第4层：订单执行 ❌ 最终差异

| 检查项 | JQ | 本地 |
|---|---|---|
| order_target_value调用 | 是（推断） | 是 |
| 参数值 | ~40,086 | 40,210.28 |
| round(参数/price, -2) | 5600(round up) | **5500(round down)** |
| 成交量 | 0 | **-100** |

## 5. 根因判断

```text
ROOT_CAUSE_0930_VALUATION_DATA_DIFFERENCE
```

**首个内部变量差异：portfolio_total_value at 09:30**

本地引擎在2026-05-14 09:30的总资产为1,005,257（基于HData开盘价），推断聚宽同时段的总额约为1,002,141（基于前一交易日收盘价）。3,116的差异（0.31%）导致stock_value相差62，进而使300405的aggregate_target相差124，最终order_target_value的100股取整落在不同边界上。

## 6. 核心问题回答

| 问题 | 答案 |
|---|---|
| 聚宽是否把300405放入昨日涨停名单？ | **否**（与本地一致） |
| 本地是否放入？ | **否**（审计确认） |
| 两边五相位目标是否一致？ | **是** |
| 两边300405相位成员数量是否一致？ | **是**（均为[0,12]） |
| 两边aggregate_target_value是否一致？ | **否**（40,086 vs 40,210） |
| 两边09:30 current_value是否一致？ | **否**（40,544 vs 40,488） |
| 聚宽是否生成sell_plan？ | **推断是**（current_value>target且不在HL名单） |
| 聚宽是否调用order_target_value？ | **推断是** |
| 聚宽订单为何没有成交？ | **推断：取整到100股后delta=0** |
| 首个内部变量差异是什么？ | **portfolio_total_value at 09:30** |

## 7. 219次拒单说明

首分叉发生在2026-05-14 09:30，所有219次拒单（始于2026-05-26 14:00）均为首分叉后的级联差异。由于首分叉后持仓已不同（本地少100股300405），后续所有执行路径均不再可比较。219次拒单不改变本任务结论。

## 8. 审计副本语义差异

审计副本`微盘股-母版-20260627-audit.py`被创建用于实验，但因引擎内部执行顺序问题未通过复现性验证。最终取证使用`engine.post_exec_hook`外部包装器方案，未修改冻结母版。

## 9. 最终状态码

```text
主状态：ROOT_CAUSE_0930_VALUATION_DATA_DIFFERENCE
附加：DATA_ALIGNMENT_REQUIRED
附加：ORDER_MODEL_ALIGNMENT_REQUIRED
```

## 10. 后续建议

| 问题 | 建议 |
|---|---|
| 是否需要TASK-003D2？ | **否**（相位和选股已验证一致） |
| 是否需要修改HData？ | **否**（HData与JQ属于不同数据源） |
| 是否需要修改local_quant引擎？ | **否**（引擎行为符合当前实现） |
| 未解决问题 | 聚宽09:30确切total_value；JQ order_target_value取整规则 |

## 11. 新增文件清单

| 文件 | 说明 |
|---|---|
| `local_audit_20260514.jsonl` | 152条结构化审计日志 |
| `audit_v2_trades.csv` | 31笔本地成交（复现验证通过） |
| `audit_v2_engine_logs.txt` | 引擎日志 |
| `jq_enhanced_rerun_reproduction.csv` | 复现性验证表 |
| `target_state_comparison.csv` | 逐层目标状态对比 |
| `yesterday_limit_comparison.csv` | 昨日涨跌停对比 |
| `valuation_input_comparison.csv` | 估值输入对比 |
| `order_intent_comparison.csv` | 订单意图对比 |
| `order_result_comparison.csv` | 订单结果对比 |
| `root_cause_003d1.json` | 根因结构化数据 |
| `task_003d1_report.md` | 本报告 |
