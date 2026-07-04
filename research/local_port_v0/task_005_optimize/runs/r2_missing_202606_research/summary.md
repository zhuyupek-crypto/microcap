# Performance Summary - r2_missing_202606_research

- Engine mode: `research`
- Window: 2026-06-01 -> 2026-06-30
- Trading days: 19
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1007284.00
- Ending value: 928977.00
- Total return: -7.77%
- Annual return (CAGR): -65.81%
- Volatility (annualized): 22.16%
- Sharpe (annualized): -3.1047
- Max drawdown: -7.78%
  - Start: 2026-06-01
  - End:   2026-06-24
- Calmar: -8.4621

## Trade Flow Metrics

- Number of fills: 53
  - Buy fills:  53
  - Sell fills: 0
- Buy turnover:  81.20%
- Sell turnover: 0.00%
- Gross turnover: 81.20%
- Annualized gross turnover: 1076.98%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 0
- Win rate: n/a
- Average return: n/a
- Median return:  n/a
- Average win:    n/a
- Average loss:   n/a
- Profit/loss ratio: n/a
- Expectancy per trade: n/a
- Average holding days: n/a
- Median holding days:  n/a

## Open Position Metrics

- Number of open positions: 13
- Open positions value: 741253.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 87
- Orders filled:    53
- Orders rejected:  34
- Fill rate: 60.92%
- Rejection reasons:
    - limit down: 34

## Notes

- No closed trades (FIFO produced zero closed lots); closed-trade metrics are null.
- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
