"""Check all 38 14:00 trades in 2020 to verify if close[14:00] == open[14:01]
for every case. This determines whether the close fix produces ANY observable
difference in the backtest.
"""
import os
import sys
import pandas as pd

os.environ.setdefault('LOCAL_QUANT_COMPATIBILITY_MODE', 'research')
os.environ.setdefault('HDATA_ROOT', r'D:\Work Space\HData')
sys.path.insert(0, r'D:\Work Space\local_quant')

from engine.data_api import DataAPI
from engine.order import get_trade_price

data_api = DataAPI(compatibility_mode='research')

# Load all 14:00 trades from the new run
trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_2020_only_close_fix\trades.csv')
trades['time'] = pd.to_datetime(trades['time'])
trades_14h = trades[trades['time'].dt.strftime('%H:%M') == '14:00'].copy()
print(f'Total 14:00 trades in 2020: {len(trades_14h)}')
print()

# For each trade, compare:
# - recorded price (from trades.csv)
# - NEW path: close of 14:00 bar (8 fields, no offset)
# - OLD path: open of 14:01 bar (6 fields, +1min offset)
results = []
for _, trade in trades_14h.iterrows():
    sec = trade['code']
    dt = trade['time']
    recorded = trade['price']

    # NEW: 8 fields, no offset
    df_new = data_api._get_price_raw(
        sec, end_date=dt, count=1,
        fields=["open", "close", "high", "low", "high_limit", "low_limit", "paused", "volume"],
        frequency="1m", fq=None
    )
    if df_new.empty:
        new_close = None
        new_vol = None
    else:
        if isinstance(df_new.columns, pd.MultiIndex):
            row = df_new.xs(sec, axis=1, level=1).iloc[0]
        else:
            row = df_new.iloc[0]
        new_close = round(float(row.get('close', 0)), 2)
        new_vol = float(row.get('volume', 0))

    # OLD: 6 fields, +1min offset
    df_old = data_api._get_price_raw(
        sec, end_date=dt + pd.Timedelta(minutes=1), count=1,
        fields=["open", "close", "high_limit", "low_limit", "paused", "volume"],
        frequency="1m", fq=None
    )
    if df_old.empty:
        old_open = None
        old_vol = None
    else:
        if isinstance(df_old.columns, pd.MultiIndex):
            row = df_old.xs(sec, axis=1, level=1).iloc[0]
        else:
            row = df_old.iloc[0]
        old_open = round(float(row.get('open', 0)), 2)
        old_vol = float(row.get('volume', 0))

    diff = abs((new_close or 0) - (old_open or 0))
    results.append({
        'time': dt,
        'code': sec,
        'recorded': recorded,
        'new_close_14h': new_close,
        'old_open_14h+1': old_open,
        'price_diff': diff,
        'new_vol': new_vol,
        'old_vol': old_vol,
    })

df = pd.DataFrame(results)
print('=== All 38 14:00 trades: NEW close[14:00] vs OLD open[14:01] ===')
print(df.to_string())
print()

# Summary
n_diff = (df['price_diff'] > 0.005).sum()
n_match = (df['price_diff'] <= 0.005).sum()
print(f'价格不同 (diff > 0.005): {n_diff} / {len(df)}')
print(f'价格相同 (diff <= 0.005): {n_match} / {len(df)}')
print()
if n_diff > 0:
    print('=== 存在差异的案例 ===')
    print(df[df['price_diff'] > 0.005].to_string())
