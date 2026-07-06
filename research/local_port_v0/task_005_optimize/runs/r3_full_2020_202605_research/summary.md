# Performance Summary - r3_full_2020_202605_research

- Engine mode: `research`
- Window: 2020-01-01 -> 2026-05-28
- Trading days: 1549
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1000069.30
- Ending value: 12850101.29
- Total return: 1184.92%
- Annual return (CAGR): 51.49%
- Volatility (annualized): 26.91%
- Sharpe (annualized): 1.8021
- Max drawdown: -24.56%
  - Start: 2024-05-17
  - End:   2024-06-24
- Calmar: 2.0970

## Trade Flow Metrics

- Number of fills: 5532
  - Buy fills:  3328
  - Sell fills: 2204
- Buy turnover:  25138.81%
- Sell turnover: 25061.33%
- Gross turnover: 50200.13%
- Annualized gross turnover: 8166.84%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 5041
- Win rate: 70.40%
- Average return: 10.66%
- Median return:  6.26%
- Average win:    18.39%
- Average loss:   7.82%
- Profit/loss ratio: 2.3523
- Expectancy per trade: 10.66%
- Average holding days: 58.96
- Median holding days:  40.00

## Open Position Metrics

- Number of open positions: 13
- Open positions value: 12850024.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 6158
- Orders filled:    5532
- Orders rejected:  626
- Fill rate: 89.83%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 614
    - limit down: 7
    - available cash is too low.: 5

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
