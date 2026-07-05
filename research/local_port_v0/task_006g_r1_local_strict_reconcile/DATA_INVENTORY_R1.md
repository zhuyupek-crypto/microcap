# TASK-006G-R1 Stage 1: Data Inventory

Generated: 2026-07-06T00:03:57.934108

## Inventory Summary

| File | Exists | Type | Start | End | Rows | Trade? | Equity? | Evidence |
|------|--------|------|-------|-----|------|--------|---------|----------|
| 母版交易记录-20250101-20251231.txt | True | jq_trade_txt | 2025-01-02 | 2025-12-29 | 647 | True | False | B |
| 母版持仓&资金记录-20250101-20250618.txt | True | jq_portfolio_txt | 2025-01-02 | 2025-06-19 | 110 | False | True | B |
| 母版交易记录-20260501-20260623.txt | True | jq_trade_txt | 2026-05-06 | 2026-06-23 | 112 | True | False | B |
| 母版持仓&资金记录-20260501-20260623.txt | True | jq_portfolio_txt | 2026-05-06 | 2026-06-24 | 35 | False | True | B |
| research\local_port_v0\task_004\jq_trades_2025.csv | True | jq_trade_csv_cleaned | 2025-01-02 | 2025-12-29 | 645 | True | False | B |
| research\local_port_v0\task_004\local_trades_2025_v2.csv | True | local_trade_csv_v2 | 2025-01-02 | 2025-12-29 | 641 | True | False | B |
| research\local_port_v0\task_003\jq_trades_normalized.csv | True | jq_trade_csv_cleaned_2026 | 2026-05-06 | 2026-06-23 | 112 | True | False | B |
| research\local_port_v0\task_003\jq_portfolio_normalized.csv | True | jq_portfolio_csv_cleaned_2026 | 2026-05-06 | 2026-06-24 | 507 | False | True | B |
| research\local_port_v0\task_003\jq_cash_enhanced.csv | True | jq_cash_csv_cleaned_2026 | 2026-05-07 | 2026-06-24 | 34 | False | True | B |
| research\local_port_v0\task_003\daily_alignment.csv | True | alignment_daily_2026 | 2026-05-06 | 2026-06-24 | 35 | False | True | B |
| research\local_port_v0\task_003\first_divergence.json | True | first_divergence_json | 2026-05-14 | 2026-05-14 | 1 | False | False | C |
| research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\equity.csv | True | r3_full_equity_reference | 2020-01-02 | 2026-05-28 | 1549 | False | False | C |
| research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\trades.csv | True | r3_full_trades_reference | 2020-01-02 | 2026-05-28 | 5005 | False | False | C |
| research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\closed_trades.csv | True | r3_full_closed_trades_reference |  |  | 4537 | False | False | C |
| research\local_port_v0\task_005_optimize\runs\r2_missing_202606_research\manifest.json | True | r2_missing_202606_manifest | 2026-06-01 | 2026-06-30 | 1 | False | False | C |

## Key Findings

### 1. 2025 Trade Records

- `母版交易记录-20250101-20251231.txt`: exists=True, 647 rows, 2025-01-02~2025-12-29
- `research\local_port_v0\task_004\jq_trades_2025.csv`: exists=True, 645 rows, 2025-01-02~2025-12-29
- `research\local_port_v0\task_004\local_trades_2025_v2.csv`: exists=True, 641 rows, 2025-01-02~2025-12-29

### 2. 2025 Equity/Cash Records

- `母版持仓&资金记录-20250101-20250618.txt`: exists=True, 110 rows, 2025-01-02~2025-06-19

### 3. 2026 Fragment Trade Records

- `母版交易记录-20260501-20260623.txt`: exists=True, 112 rows, 2026-05-06~2026-06-23
- `research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\trades.csv`: exists=True, 5005 rows, 2020-01-02~2026-05-28
- `research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\closed_trades.csv`: exists=True, 4537 rows, ~

### 4. 2026 Fragment Equity/Cash Records

- `母版持仓&资金记录-20260501-20260623.txt`: exists=True, 35 rows, 2026-05-06~2026-06-24
- `research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\equity.csv`: exists=True, 1549 rows, 2020-01-02~2026-05-28

### 5. Local Reference Runs (NOT for direct slice use)

- `research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\equity.csv`: exists=True, 1549 rows, 2020-01-02~2026-05-28
- `research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\trades.csv`: exists=True, 5005 rows, 2020-01-02~2026-05-28
- `research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\closed_trades.csv`: exists=True, 4537 rows, ~

## Implications for Strict Reconciliation

- **2025 equity records only cover H1**: full-year A-level equity reconciliation NOT possible; will downgrade 2025 H1 equity to A/B and full-year equity to C.
- **r3_full outputs are reference-only**: cannot be used as same-start baseline; must rerun local backtest from 2025-01-01 / 2026-05-01 with empty portfolio.
- **task_003 normalized CSVs are preferred** for 2026 fragment (already cleaned).
- **task_004 jq_trades_2025.csv is preferred** for 2025 trade reconciliation.
