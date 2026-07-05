# Performance Summary - r1_2026m05_research

- Engine mode: `research`
- Window: 2026-05-01 -> 2026-06-24
- Trading days: 35
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1001161.00
- Ending value: 790987.23
- Total return: -20.99%
- Annual return (CAGR): -81.67%
- Volatility (annualized): 30.75%
- Sharpe (annualized): -2.7536
- Max drawdown: -21.64%
  - Start: 2026-05-14
  - End:   2026-06-24
- Calmar: -3.7743

## Trade Flow Metrics

- Number of fills: 94
  - Buy fills:  76
  - Sell fills: 18
- Buy turnover:  124.36%
- Sell turnover: 24.48%
- Gross turnover: 148.83%
- Annualized gross turnover: 1071.61%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 26
- Win rate: 30.77%
- Average return: -5.61%
- Median return:  -8.68%
- Average win:    7.01%
- Average loss:   11.21%
- Profit/loss ratio: 0.6252
- Expectancy per trade: -5.61%
- Average holding days: 22.88
- Median holding days:  22.50

## Open Position Metrics

- Number of open positions: 13
- Open positions value: 790530.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 126
- Orders filled:    94
- Orders rejected:  32
- Fill rate: 74.60%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 5
    - limit down: 27

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
