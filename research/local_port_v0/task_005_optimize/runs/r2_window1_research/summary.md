# Performance Summary - r2_window1_research

- Engine mode: `research`
- Window: 2024-05-01 -> 2024-06-10
- Trading days: 25
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1006354.00
- Ending value: 856452.69
- Total return: -14.90%
- Annual return (CAGR): -80.32%
- Volatility (annualized): 45.59%
- Sharpe (annualized): -1.8278
- Max drawdown: -22.69%
  - Start: 2024-05-17
  - End:   2024-06-06
- Calmar: -3.5400

## Trade Flow Metrics

- Number of fills: 99
  - Buy fills:  75
  - Sell fills: 24
- Buy turnover:  123.95%
- Sell turnover: 24.03%
- Gross turnover: 147.98%
- Annualized gross turnover: 1491.68%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 31
- Win rate: 41.94%
- Average return: -2.00%
- Median return:  -0.65%
- Average win:    5.16%
- Average loss:   7.59%
- Profit/loss ratio: 0.6796
- Expectancy per trade: -2.00%
- Average holding days: 21.94
- Median holding days:  21.00

## Open Position Metrics

- Number of open positions: 15
- Open positions value: 856373.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 107
- Orders filled:    99
- Orders rejected:  8
- Fill rate: 92.52%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 8

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
