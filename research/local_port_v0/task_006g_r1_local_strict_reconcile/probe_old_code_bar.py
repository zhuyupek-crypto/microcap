"""Probe what OLD order.py code actually returns for 14:00 trades.

OLD code:
    df = data_api._get_price_raw(
        security, end_date=current_dt + pd.Timedelta(minutes=1), count=1,
        fields=["open", "close", "high_limit", "low_limit", "paused", "volume"],  # 6 fields
        frequency="1m", fq=None
    )
    field = "avg"
    if is_research:
        price = round(float(row.get("open", 0)), decimals)  # fallback to open

Question: Does the 6-field query with end_date=14:01 return the 14:00 bar or 14:01 bar?
If it returns 14:00 bar, then row.get("open") = open[14:00] (not open[14:01]).
If it returns 14:01 bar, then row.get("open") = open[14:01].

Previous verify_all_14h_trades.py showed 6-field query returns 14:01 bar.
But compare_pre_vs_post_close_fix.py showed pre_close_fix prices == close[14:00].

This is contradictory. Let me re-verify with the SAME data_api instance state
as during backtest (maybe caching matters).
"""
import os
import sys
import pandas as pd

os.environ.setdefault('LOCAL_QUANT_COMPATIBILITY_MODE', 'research')
os.environ.setdefault('HDATA_ROOT', r'D:\Work Space\HData')
sys.path.insert(0, r'D:\Work Space\local_quant')

from engine.data_api import DataAPI

data_api = DataAPI(compatibility_mode='research')

# Test case: 2020-03-13 603991.XSHG (one of the 11 cases where close != open)
# close[14:00] = 24.76, open[14:01] = 24.79
security = '603991.XSHG'
current_dt = pd.Timestamp('2020-03-13 14:00:00')

print(f'=== Probe OLD code behavior for {security} @ {current_dt} ===')
print()

# OLD code: 6 fields, end_date=14:01
df_old = data_api._get_price_raw(
    security, end_date=current_dt + pd.Timedelta(minutes=1), count=1,
    fields=["open", "close", "high_limit", "low_limit", "paused", "volume"],
    frequency="1m", fq=None
)
print(f'OLD code (6 fields, end=14:01):')
if not df_old.empty:
    if isinstance(df_old.columns, pd.MultiIndex):
        row = df_old.xs(security, axis=1, level=1).iloc[0]
    else:
        row = df_old.iloc[0]
    print(f'  index = {df_old.index[0]}')
    print(f'  open = {row.get("open")}, close = {row.get("close")}, volume = {row.get("volume")}')
    print(f'  -> OLD code would return open = {row.get("open")}')
else:
    print('  EMPTY')

print()

# NEW code: 8 fields, end_date=14:00
df_new = data_api._get_price_raw(
    security, end_date=current_dt, count=1,
    fields=["open", "close", "high", "low", "high_limit", "low_limit", "paused", "volume"],
    frequency="1m", fq=None
)
print(f'NEW code (8 fields, end=14:00):')
if not df_new.empty:
    if isinstance(df_new.columns, pd.MultiIndex):
        row = df_new.xs(security, axis=1, level=1).iloc[0]
    else:
        row = df_new.iloc[0]
    print(f'  index = {df_new.index[0]}')
    print(f'  open = {row.get("open")}, close = {row.get("close")}, volume = {row.get("volume")}')
    print(f'  -> NEW code returns close = {row.get("close")}')
else:
    print('  EMPTY')

print()

# Recorded price in pre_close_fix and close_fix
import pandas as pd
pre_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_pre_close_fix\trades.csv')
pre_trades['time'] = pd.to_datetime(pre_trades['time'])
match = pre_trades[(pre_trades['time'] == current_dt) & (pre_trades['code'] == security)]
print(f'pre_close_fix recorded price: {match["price"].iloc[0] if not match.empty else "NOT FOUND"}')

post_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_only_close_fix\trades.csv')
post_trades['time'] = pd.to_datetime(post_trades['time'])
match2 = post_trades[(post_trades['time'] == current_dt) & (post_trades['code'] == security)]
print(f'close_fix recorded price: {match2["price"].iloc[0] if not match2.empty else "NOT FOUND"}')

print()
print('=== Conclusion ===')
print('If OLD code returns open[14:01]=24.79, pre_close_fix price should be 24.79')
print('If OLD code returns open[14:00]=24.76, pre_close_fix price should be 24.76')
print('If pre_close_fix price == 24.76, then 6-field query actually returns 14:00 bar (not 14:01)')
