# Performance Summary - r2_window2_research

- Engine mode: `research`
- Window: 2025-02-01 -> 2025-03-31
- Trading days: 39
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1008581.00
- Ending value: 1000507.64
- Total return: -0.80%
- Annual return (CAGR): -5.06%
- Volatility (annualized): 26.86%
- Sharpe (annualized): -0.3000
- Max drawdown: -11.62%
  - Start: 2025-03-20
  - End:   2025-03-31
- Calmar: -0.4354

## Trade Flow Metrics

- Number of fills: 158
  - Buy fills:  101
  - Sell fills: 57
- Buy turnover:  157.47%
- Sell turnover: 60.94%
- Gross turnover: 218.41%
- Annualized gross turnover: 1411.27%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 75
- Win rate: 93.33%
- Average return: 17.01%
- Median return:  10.76%
- Average win:    18.65%
- Average loss:   5.94%
- Profit/loss ratio: 3.1377
- Expectancy per trade: 17.01%
- Average holding days: 21.88
- Median holding days:  21.00

## Open Position Metrics

- Number of open positions: 12
- Open positions value: 967250.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 176
- Orders filled:    158
- Orders rejected:  18
- Fill rate: 89.77%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 17
    - limit down: 1

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
