# Performance Summary - r3_2024_202605_research

- Engine mode: `research`
- Window: 2024-01-01 -> 2026-05-28
- Trading days: 579
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1000168.30
- Ending value: 2693218.83
- Total return: 169.28%
- Annual return (CAGR): 53.90%
- Volatility (annualized): 33.13%
- Sharpe (annualized): 1.5364
- Max drawdown: -24.55%
  - Start: 2024-05-17
  - End:   2024-06-24
- Calmar: 2.1957

## Trade Flow Metrics

- Number of fills: 1936
  - Buy fills:  1199
  - Sell fills: 737
- Buy turnover:  3885.43%
- Sell turnover: 3789.09%
- Gross turnover: 7674.52%
- Annualized gross turnover: 3340.21%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 1719
- Win rate: 64.51%
- Average return: 13.62%
- Median return:  6.97%
- Average win:    26.30%
- Average loss:   9.52%
- Profit/loss ratio: 2.7637
- Expectancy per trade: 13.62%
- Average holding days: 57.95
- Median holding days:  39.00

## Open Position Metrics

- Number of open positions: 13
- Open positions value: 2693038.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 2154
- Orders filled:    1936
- Orders rejected:  218
- Fill rate: 89.88%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 216
    - limit down: 2

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
