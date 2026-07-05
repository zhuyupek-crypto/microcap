# TASK-006G-R1 Equity Reconciliation: 2025 H1

## Inputs

- JQ: `D:\Work Space\他山之石\微盘股\research\local_port_v0\task_006g_r1_local_strict_reconcile\outputs\JQ_2025_EQUITY_NORMALIZED.csv`
- Local: `D:\Work Space\他山之石\微盘股\research\local_port_v0\task_006g_r1_local_strict_reconcile\runs\r1_2025_research\equity.csv`

## Evidence Level: B

## Coverage Note

2025 JQ equity records only cover H1 (2025-01-02 ~ 2025-06-19). Full-year A-level equity reconciliation NOT possible. This recon is H1 only; full-year equity evidence level is C.

## Statistics

| Metric | Value |
|--------|-------|
| period_start | 2025-01-02 |
| period_end | 2025-06-18 |
| jq_start_asset | 999901.0 |
| local_start_asset | 999901.0 |
| jq_end_asset | 1065673.84 |
| local_end_asset | 1065742.5499999998 |
| jq_total_return | 0.06577935215586361 |
| local_total_return | 0.06584806895882678 |
| return_diff | -6.871680296316462e-05 |
| jq_max_drawdown | -0.11626484532595925 |
| local_max_drawdown | -0.11612233612914231 |
| max_drawdown_diff | -0.00014250919681693675 |
| jq_daily_return_corr | 0.9999990089991129 |
| mean_abs_asset_diff | 65.91761467889819 |
| max_abs_asset_diff | 126.87000000011176 |
| first_equity_divergence_date | 2025-02-18 |
| first_equity_divergence_reason | asset_diff > 1.0 |
