# Performance Summary - r3_2020_minute_close

- Engine mode: `research`
- Window: 2020-01-01 -> 2020-12-31
- Trading days: 243
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1000069.30
- Ending value: 1320735.74
- Total return: 32.06%
- Annual return (CAGR): 33.43%
- Volatility (annualized): 24.62%
- Sharpe (annualized): 1.2360
- Max drawdown: -14.72%
  - Start: 2020-09-08
  - End:   2020-12-28
- Calmar: 2.2712

## Trade Flow Metrics

- Number of fills: 856
  - Buy fills:  514
  - Sell fills: 342
- Buy turnover:  921.50%
- Sell turnover: 822.88%
- Gross turnover: 1744.38%
- Annualized gross turnover: 1808.99%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 652
- Win rate: 72.70%
- Average return: 10.42%
- Median return:  8.92%
- Average win:    17.48%
- Average loss:   8.43%
- Profit/loss ratio: 2.0745
- Expectancy per trade: 10.42%
- Average holding days: 52.49
- Median holding days:  41.00

## Open Position Metrics

- Number of open positions: 14
- Open positions value: 1317318.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 958
- Orders filled:    856
- Orders rejected:  102
- Fill rate: 89.35%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 100
    - limit down: 2

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
