# Performance Summary - r3_full_2020_202605_research

- Engine mode: `research`
- Window: 2020-01-01 -> 2026-05-28
- Trading days: 1549
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1000069.30
- Ending value: 11287258.87
- Total return: 1028.65%
- Annual return (CAGR): 48.33%
- Volatility (annualized): 25.81%
- Sharpe (annualized): 1.7565
- Max drawdown: -23.20%
  - Start: 2024-05-17
  - End:   2024-06-24
- Calmar: 2.0834

## Trade Flow Metrics

- Number of fills: 5005
  - Buy fills:  2977
  - Sell fills: 2028
- Buy turnover:  21942.81%
- Sell turnover: 21862.49%
- Gross turnover: 43805.30%
- Annualized gross turnover: 7126.49%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 4537
- Win rate: 69.80%
- Average return: 10.67%
- Median return:  6.38%
- Average win:    18.61%
- Average loss:   7.78%
- Profit/loss ratio: 2.3914
- Expectancy per trade: 10.67%
- Average holding days: 59.31
- Median holding days:  41.00

## Open Position Metrics

- Number of open positions: 15
- Open positions value: 11287251.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 6467
- Orders filled:    5005
- Orders rejected:  1462
- Fill rate: 77.39%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 1452
    - available cash is too low.: 2
    - sell amount 3000 exceeds closeable amount 2300: 1
    - limit down: 6
    - limit up: 1

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
