# Performance Summary - r3_2022_2023_research

- Engine mode: `research`
- Window: 2022-01-01 -> 2023-12-31
- Trading days: 484
- Initial cash: 1000000.0

## Equity Metrics

- Initial value: 1000019.80
- Ending value: 2021851.71
- Total return: 102.18%
- Annual return (CAGR): 44.27%
- Volatility (annualized): 20.67%
- Sharpe (annualized): 1.9965
- Max drawdown: -11.98%
  - Start: 2022-03-03
  - End:   2022-03-15
- Calmar: 3.6966

## Trade Flow Metrics

- Number of fills: 1321
  - Buy fills:  797
  - Sell fills: 524
- Buy turnover:  1814.28%
- Sell turnover: 1716.25%
- Gross turnover: 3530.53%
- Annualized gross turnover: 1838.21%

## Closed Trade Metrics (FIFO, gross of costs)

- Number of closed trades: 1075
- Win rate: 74.60%
- Average return: 10.70%
- Median return:  5.97%
- Average win:    15.76%
- Average loss:   4.27%
- Profit/loss ratio: 3.6897
- Expectancy per trade: 10.70%
- Average holding days: 57.75
- Median holding days:  38.00

## Open Position Metrics

- Number of open positions: 13
- Open positions value: 2021415.00
- Note: Open positions are excluded from closed-trade win rate. Unrealized P&L is not computed (would require market data).

## Execution Quality

- Orders submitted: 1837
- Orders filled:    1321
- Orders rejected:  516
- Fill rate: 71.91%
- Rejection reasons:
    - cash insufficient for even 1 lot.: 506
    - limit down: 3
    - available cash is too low.: 7

## Notes

- Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.
- risk_free_rate = 0.03; trading_days_per_year = 252.
- Turnover denominator = manifest.initial_cash = 1000000.00 (not equity first value).
