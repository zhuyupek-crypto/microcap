"""Check old trades.csv to see if the 11 differing cases have old_open or new_close as price.

If old trades.csv price == old_open_14h+1, then old code returned open -> fix changed behavior.
If old trades.csv price == new_close_14h, then old code also returned close -> fix was a no-op.
"""
import pandas as pd

# Load old and new trades.csv
old_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\trades.csv')
old_trades['time'] = pd.to_datetime(old_trades['time'])
old_trades = old_trades[old_trades['time'].dt.year == 2020].copy()

new_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_only_close_fix\trades.csv')
new_trades['time'] = pd.to_datetime(new_trades['time'])

# The 11 cases where close[14:00] != open[14:01]
cases = [
    ('2020-03-13 14:00:00', '603991.XSHG', 24.76, 24.79),
    ('2020-03-30 14:00:00', '300029.XSHE', 6.32, 6.33),
    ('2020-05-21 14:00:00', '600520.XSHG', 8.44, 8.43),
    ('2020-05-27 14:00:00', '600520.XSHG', 10.03, 10.08),
    ('2020-07-07 14:00:00', '002473.XSHE', 8.88, 8.89),
    ('2020-08-06 14:00:00', '300312.XSHE', 4.93, 4.92),
    ('2020-08-11 14:00:00', '002209.XSHE', 8.95, 8.91),
    ('2020-09-02 14:00:00', '000502.XSHE', 8.45, 8.44),
    ('2020-09-09 14:00:00', '300736.XSHE', 15.55, 15.53),
    ('2020-09-15 14:00:00', '300665.XSHE', 13.63, 13.64),
    ('2020-10-19 14:00:00', '002633.XSHE', 8.90, 8.91),
]

print(f'{"time":<22} {"code":<12} {"new_close":<10} {"old_open":<10} {"OLD_trade_price":<18} {"NEW_trade_price":<18} {"OLD_match":<12} {"NEW_match":<12}')
print('-' * 130)
for t_str, code, new_close, old_open in cases:
    t = pd.Timestamp(t_str)
    old_match = old_trades[(old_trades['time'] == t) & (old_trades['code'] == code)]
    new_match = new_trades[(new_trades['time'] == t) & (new_trades['code'] == code)]
    old_price = old_match['price'].iloc[0] if not old_match.empty else None
    new_price = new_match['price'].iloc[0] if not new_match.empty else None
    old_m = 'close' if old_price == new_close else ('open' if old_price == old_open else '?')
    new_m = 'close' if new_price == new_close else ('open' if new_price == old_open else '?')
    print(f'{t_str:<22} {code:<12} {new_close:<10} {old_open:<10} {str(old_price):<18} {str(new_price):<18} {old_m:<12} {new_m:<12}')
