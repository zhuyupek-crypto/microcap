# Performance Summary - r3_2020_2021_research

- Engine mode: `research`
- Window: 2020-01-01 -> 2021-12-31
- Trading days: 486
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1000069.30
- Ending value: 2212484.94
- Total return: 121.23%
- Annual return (CAGR): 50.94%
- Volatility (annualized): 22.80%
- Sharpe (annualized): 2.1027
- Max drawdown: -14.87%
  - Start: 2021-09-08
  - End:   2021-10-28
- Calmar: 3.4257

## Trade Flow Metrics

- Number of fills: 1595
  - Buy fills:  954
  - Sell fills: 641
- Buy turnover:  2030.21%
- Sell turnover: 1932.54%
- Gross turnover: 3962.76%
- Annualized gross turnover: 2054.76%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 1321
- Win rate: 71.23%
- Average return: 9.33%
- Median return:  8.13%
- Average win:    16.55%
- Average loss:   8.59%
- Profit/loss ratio: 1.9254
- Expectancy per trade: 9.33%
- Average holding days: 55.84
- Median holding days:  39.00

## Open Position Metrics

- Number of open positions: 14
- Open positions value: 2211690.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 1846
- Orders filled:    1595
- Orders rejected:  251
- Fill rate: 86.40%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 246
    - available cash is too low.: 2
    - sell amount 3000 exceeds closeable amount 2300: 1
    - limit down: 2

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
