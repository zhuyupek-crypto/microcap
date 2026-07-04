# Performance Summary - r2_window3_research

- Engine mode: `research`
- Window: 2026-05-01 -> 2026-05-28
- Trading days: 17
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1001161.00
- Ending value: 933795.26
- Total return: -6.73%
- Annual return (CAGR): -64.39%
- Volatility (annualized): 22.61%
- Sharpe (annualized): -2.9802
- Max drawdown: -7.49%
  - Start: 2026-05-14
  - End:   2026-05-28
- Calmar: -8.5964

## Trade Flow Metrics

- Number of fills: 63
  - Buy fills:  58
  - Sell fills: 5
- Buy turnover:  107.30%
- Sell turnover: 7.87%
- Gross turnover: 115.17%
- Annualized gross turnover: 1707.28%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 6
- Win rate: 50.00%
- Average return: 5.00%
- Median return:  3.81%
- Average win:    12.40%
- Average loss:   2.41%
- Profit/loss ratio: 5.1443
- Expectancy per trade: 5.00%
- Average holding days: 18.83
- Median holding days:  21.00

## Open Position Metrics

- Number of open positions: 13
- Open positions value: 928472.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 63
- Orders filled:    63
- Orders rejected:  0
- Fill rate: 100.00%
- Rejection reasons:
    - (none)

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
