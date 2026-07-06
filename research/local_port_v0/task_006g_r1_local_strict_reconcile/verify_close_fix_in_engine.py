"""Verify close fix actually takes effect inside the engine path.

Picks the 2020-02-19 300412.XSHE 14:00 trade (recorded price=8.73) and
calls engine's actual order path to check what price is returned.

Also directly calls get_trade_price to compare with the OLD code's expected
output (open of 14:01 bar) and the NEW code's expected output (close of 14:00 bar).
"""
import os
import sys
import pandas as pd

# Setup paths
os.environ.setdefault('LOCAL_QUANT_COMPATIBILITY_MODE', 'research')
os.environ.setdefault('HDATA_ROOT', r'D:\Work Space\HData')
sys.path.insert(0, r'D:\Work Space\local_quant')

from engine.data_api import DataAPI
from engine.order import get_trade_price

# Use the same data root as the actual backtest
data_api = DataAPI(compatibility_mode='research')

# Test case: 2020-02-19 14:00 300412.XSHE, recorded trade price = 8.73
security = '300412.XSHE'
current_dt = pd.Timestamp('2020-02-19 14:00:00')
current_time = '14:00'

print(f'=== Verify get_trade_price for {security} @ {current_dt} ===')
print(f'compatibility_mode = {data_api.compatibility_mode}')
print()

# Call the actual get_trade_price function (NEW code path)
price, high_limit, low_limit, paused, volume = get_trade_price(
    data_api, current_dt, current_time, security
)
print(f'NEW code path result:')
print(f'  price = {price}')
print(f'  high_limit = {high_limit}')
print(f'  low_limit = {low_limit}')
print(f'  paused = {paused}')
print(f'  volume = {volume}')
print()

# Compare with the recorded trade price
recorded_price = 8.73
print(f'Recorded trade price: {recorded_price}')
print(f'Match? {abs(price - recorded_price) < 1e-6}')
print()

# Now manually probe what the OLD code would have returned
# OLD code: end_date=current_dt + 1min, 6 fields, field='avg'
# Research mode fallback: avg -> open
print('=== Manual probe of OLD vs NEW data_api._get_price_raw calls ===')

# NEW path: end_date=current_dt (no offset), 8 fields, frequency=1m
df_new = data_api._get_price_raw(
    security, end_date=current_dt, count=1,
    fields=["open", "close", "high", "low", "high_limit", "low_limit", "paused", "volume"],
    frequency="1m", fq=None
)
print(f'NEW path (8 fields, no offset, end={current_dt}):')
if not df_new.empty:
    if isinstance(df_new.columns, pd.MultiIndex):
        row = df_new.xs(security, axis=1, level=1).iloc[0]
    else:
        row = df_new.iloc[0]
    print(f'  open={row.get("open")}, close={row.get("close")}, volume={row.get("volume")}')
    print(f'  -> NEW code returns close = {row.get("close")}')
else:
    print('  EMPTY')

print()

# OLD path: end_date=current_dt + 1min, 6 fields (with -1min internal offset)
df_old = data_api._get_price_raw(
    security, end_date=current_dt + pd.Timedelta(minutes=1), count=1,
    fields=["open", "close", "high_limit", "low_limit", "paused", "volume"],
    frequency="1m", fq=None
)
print(f'OLD path (6 fields, +1min offset, end={current_dt + pd.Timedelta(minutes=1)}):')
if not df_old.empty:
    if isinstance(df_old.columns, pd.MultiIndex):
        row = df_old.xs(security, axis=1, level=1).iloc[0]
    else:
        row = df_old.iloc[0]
    print(f'  open={row.get("open")}, close={row.get("close")}, volume={row.get("volume")}')
    print(f'  -> OLD code returns open (research fallback) = {row.get("open")}')
else:
    print('  EMPTY')

print()

# Also check: what does the 4-field query return?
df_4 = data_api._get_price_raw(
    security, end_date=current_dt, count=1,
    fields=["close", "high_limit", "low_limit", "paused"],
    frequency="1m", fq=None
)
print(f'4-field query (end={current_dt}):')
if not df_4.empty:
    if isinstance(df_4.columns, pd.MultiIndex):
        row = df_4.xs(security, axis=1, level=1).iloc[0]
    else:
        row = df_4.iloc[0]
    print(f'  close={row.get("close")}')
else:
    print('  EMPTY')
