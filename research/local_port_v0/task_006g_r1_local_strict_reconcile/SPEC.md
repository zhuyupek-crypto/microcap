# TASK-006G-R1: 2025/2026 聚宽母版 vs 本地母版局部严格绩效对账

## 一、任务背景

TASK-006G 已完成"聚宽母版 vs 本地母版"的宏观归因，但其中一个局部证据仍需补强：

006G 已做：
- 聚宽母版 68.24% vs 本地母版 48.33% 的宏观比较；
- 2025 全年交易级匹配；
- 2026-05~06 片段交易/资金局部对齐；
- 聚宽 68.24% 因缺完整长周期净值/逐笔数据，被降为 C 级宏观参考。

006G 仍有一个不足：
> 2025 和 2026 片段虽然有聚宽母版交易记录、资金/持仓记录，但本地对比主要使用 r3_full 的切片。r3_full 是从 2020 累积到 2025/2026 的净值和持仓，不能严格代表"同起点、同资金"的局部绩效对账。

本任务补做：
> **2025全年、2026片段的聚宽母版 vs 本地母版同起点独立回测严格对账。**

## 二、任务目标

只回答一个问题：
> 在已有聚宽母版交易/资金数据覆盖的局部区间内，本地化母版和聚宽母版到底差多少？差异来自哪里？

必须分别完成：
1. **2025 全年对账**：聚宽母版交易记录 vs 本地母版 2025 独立回测交易记录；聚宽母版资金/持仓记录 vs 本地母版 2025 独立回测净值/现金/持仓；输出日度净值差异、逐笔交易差异、首个分叉点、差异归因。
2. **2026-05~06 片段对账**：聚宽母版交易记录 vs 本地母版同起点片段回测；聚宽母版资金/持仓记录 vs 本地母版同起点片段净值/现金/持仓；验证 2026-05-14 首分叉及后续级联残余；输出片段绩效差异。
3. **最终判断**：2025 局部是否能做到 A 级严格对账；2026 片段是否能做到 A 级严格对账；局部差异是否会影响 006G 的大结论；本地 Research 是否仍作为实盘基线。

## 三、输入数据

重点检查以下文件：
```
母版交易记录-20250101-20251231.txt
母版持仓&资金记录-20250101-20250618.txt
母版交易记录-20260501-20260623.txt
母版持仓&资金记录-20260501-20260623.txt
research/local_port_v0/task_004/jq_trades_2025.csv
research/local_port_v0/task_004/local_trades_2025_v2.csv
research/local_port_v0/task_003/daily_alignment.csv
research/local_port_v0/task_003/trade_alignment.csv
research/local_port_v0/task_003/first_divergence.json
research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/equity.csv
research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/trades.csv
research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research/closed_trades.csv
```

如果存在更多已清洗的聚宽资金/持仓CSV，应优先使用清洗版，而不是重新解析txt。

## 四、工作目录

```
research/local_port_v0/task_006g_r1_local_strict_reconcile/
├── SPEC.md
├── data_inventory_r1.py
├── parse_jq_logs_r1.py
├── run_local_periods_r1.py
├── reconcile_trades_r1.py
├── reconcile_equity_r1.py
├── explain_diffs_r1.py
├── outputs/
│   ├── DATA_INVENTORY_R1.csv
│   ├── JQ_2025_TRADES_NORMALIZED.csv
│   ├── JQ_2025_EQUITY_NORMALIZED.csv
│   ├── LOCAL_2025_TRADES.csv
│   ├── LOCAL_2025_EQUITY.csv
│   ├── TRADE_RECON_2025.csv
│   ├── EQUITY_RECON_2025.csv
│   ├── DIFF_ATTRIBUTION_2025.csv
│   ├── JQ_2026_FRAGMENT_TRADES_NORMALIZED.csv
│   ├── JQ_2026_FRAGMENT_EQUITY_NORMALIZED.csv
│   ├── LOCAL_2026_FRAGMENT_TRADES.csv
│   ├── LOCAL_2026_FRAGMENT_EQUITY.csv
│   ├── TRADE_RECON_2026_FRAGMENT.csv
│   ├── EQUITY_RECON_2026_FRAGMENT.csv
│   ├── DIFF_ATTRIBUTION_2026_FRAGMENT.csv
│   └── TASK_006G_R1_SUMMARY.csv
└── TASK_006G_R1_REPORT.md
```

## 五至十一、阶段一至七

详见用户原始规格书。每个阶段的输入输出严格要求：

### 阶段一：数据盘点
输出：`outputs/DATA_INVENTORY_R1.csv` + `DATA_INVENTORY_R1.md`

### 阶段二：聚宽日志标准化
编写：`parse_jq_logs_r1.py`
输出：`outputs/JQ_2025_TRADES_NORMALIZED.csv`、`outputs/JQ_2025_EQUITY_NORMALIZED.csv`、`outputs/JQ_2026_FRAGMENT_TRADES_NORMALIZED.csv`、`outputs/JQ_2026_FRAGMENT_EQUITY_NORMALIZED.csv`

### 阶段三：本地同起点独立回测
关键要求：不能直接用 r3_full 的2025/2026切片作为严格净值对照。
- 2025独立回测：start=2025-01-01, end=2025-12-31, cash=1,000,000, mode=research
- 2026片段独立回测：start=2026-05-01 (或05-06), end=2026-06-24, cash=1,000,000, mode=research

### 阶段四：2025交易对账
编写：`reconcile_trades_r1.py` 输出 `outputs/TRADE_RECON_2025.csv` + `TRADE_RECON_2025.md`

### 阶段五：2025资金/净值对账
编写：`reconcile_equity_r1.py` 输出 `outputs/EQUITY_RECON_2025.csv` + `EQUITY_RECON_2025.md`

### 阶段六：2026片段交易/资金对账
重复阶段四、五，但输出 2026_FRAGMENT 命名

### 阶段七：差异归因
编写：`explain_diffs_r1.py` 输出 `outputs/DIFF_ATTRIBUTION_2025.csv`、`outputs/DIFF_ATTRIBUTION_2026_FRAGMENT.csv` + 两个md

## 十二、最终汇总报告
输出：`TASK_006G_R1_REPORT.md` + `outputs/TASK_006G_R1_SUMMARY.csv`

## 十三、证据等级
- A = 同起点、同资金、同区间、交易+资金+持仓可逐日/逐笔对齐
- B = 交易可对齐，但资金/持仓覆盖不完整或起始状态不一致
- C = 只有摘要或无法严格对齐

## 十四、禁止事项
1. 禁止修改母版策略代码；
2. 禁止修改回测引擎核心逻辑；
3. 禁止把 r3_full 的2025切片当成同起点独立回测；
4. 禁止把2025 H1资金结论外推为2025全年；
5. 禁止把2026片段结论外推为全周期；
6. 禁止把JQ qty=0导出缺陷算作真实策略差异；
7. 禁止在起始状态不一致时声称A级净值对账；
8. 禁止为了对齐聚宽结果而手动改成交价、成交量、费用；
9. 禁止重新优化策略；
10. 禁止改变006E纸面交易方向，除非发现本地回测重大错误。

## 十五、验收标准
1. 完成数据盘点；
2. 标准化JQ交易和资金/持仓记录；
3. 补跑2025本地同起点独立回测；
4. 补跑2026片段本地同起点独立回测；
5. 输出2025交易对账；
6. 输出2025资金/净值对账，或明确资金数据不足导致降级；
7. 输出2026片段交易对账；
8. 输出2026片段资金/净值对账；
9. 输出差异归因矩阵；
10. 输出TASK_006G_R1_REPORT.md；
11. 明确每个结论的证据等级；
12. 明确是否修正006G；
13. 明确是否影响006E纸面交易方向；
14. 不修改策略；
15. 不修改引擎；
16. 不做策略优化。
