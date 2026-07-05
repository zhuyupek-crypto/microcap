# Performance Summary - r1_2025_research

- Engine mode: `research`
- Window: 2025-01-01 -> 2025-12-31
- Trading days: 243
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 999901.00
- Ending value: 1498467.78
- Total return: 49.86%
- Annual return (CAGR): 52.12%
- Volatility (annualized): 23.90%
- Sharpe (annualized): 2.0557
- Max drawdown: -13.71%
  - Start: 2025-11-17
  - End:   2025-12-16
- Calmar: 3.8012

## Trade Flow Metrics

- Number of fills: 641
  - Buy fills:  411
  - Sell fills: 230
- Buy turnover:  714.88%
- Sell turnover: 615.83%
- Gross turnover: 1330.71%
- Annualized gross turnover: 1380.00%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 409
- Win rate: 79.71%
- Average return: 18.00%
- Median return:  12.51%
- Average win:    24.44%
- Average loss:   7.39%
- Profit/loss ratio: 3.3053
- Expectancy per trade: 18.00%
- Average holding days: 55.29
- Median holding days:  37.00

## Open Position Metrics

- Number of open positions: 12
- Open positions value: 1496490.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 736
- Orders filled:    641
- Orders rejected:  95
- Fill rate: 87.09%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 94
    - limit down: 1

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
