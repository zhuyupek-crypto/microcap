# TASK-006G-R1 Equity Reconciliation: 2026-05~06 fragment

## Inputs

- JQ: `D:\Work Space\他山之石\微盘股\research\local_port_v0\task_006g_r1_local_strict_reconcile\outputs\JQ_2026_FRAGMENT_EQUITY_NORMALIZED.csv`
- Local: `D:\Work Space\他山之石\微盘股\research\local_port_v0\task_006g_r1_local_strict_reconcile\runs\r1_2026m05_research\equity.csv`

## Evidence Level: A

## Coverage Note

2026 fragment JQ equity covers 2026-05-06 ~ 2026-06-24. Both JQ and local start from 1M cash / empty portfolio on 2026-05-06.

## Statistics

| Metric | Value |
|--------|-------|
| period_start | 2026-05-06 |
| period_end | 2026-06-24 |
| jq_start_asset | 1001161.0 |
| local_start_asset | 1001161.0 |
| jq_end_asset | 788859.06 |
| local_end_asset | 790987.23 |
| jq_total_return | -0.21205574328204946 |
| local_total_return | -0.2099300412221411 |
| return_diff | -0.002125702059908363 |
| jq_max_drawdown | -0.2184910318454931 |
| local_max_drawdown | -0.216382690793091 |
| max_drawdown_diff | -0.0021083410524020962 |
| jq_daily_return_corr | 0.9993466112816252 |
| mean_abs_asset_diff | 472.83628571429625 |
| max_abs_asset_diff | 3597.1699999999255 |
| first_equity_divergence_date | 2026-06-01 |
| first_equity_divergence_reason | asset_diff > 1.0 |
