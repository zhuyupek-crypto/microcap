"""Check if pre_fallback4 trades used close[14:00] or open[14:01] for 14:00 trades.

This determines whether pre_fallback4 backup was made BEFORE or AFTER the close fix.
- If pre_fallback4 14:00 trade prices == open[14:01], then pre_fallback4 is BEFORE close fix
- If pre_fallback4 14:00 trade prices == close[14:00], then pre_fallback4 is AFTER close fix
"""
import os
import sys
import pandas as pd

os.environ.setdefault('LOCAL_QUANT_COMPATIBILITY_MODE', 'research')
os.environ.setdefault('HDATA_ROOT', r'D:\Work Space\HData')
sys.path.insert(0, r'D:\Work Space\local_quant')

from engine.data_api import DataAPI

data_api = DataAPI(compatibility_mode='research')

# Load pre_fallback4 trades
old_trades = pd.read_csv(r'd:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize\runs\r3_full_2020_202605_research\trades_pre_fallback4.csv')
old_trades['time'] = pd.to_datetime(old_trades['time'])
old_trades = old_trades[old_trades['time'].dt.year == 2020].copy()
old_trades_14h = old_trades[old_trades['time'].dt.strftime('%H:%M') == '14:00'].copy()
print(f'pre_fallback4 14:00 trades in 2020: {len(old_trades_14h)}')
print()

# For each 14:00 trade, check if recorded price matches close[14:00] or open[14:01]
results = []
for _, trade in old_trades_14h.iterrows():
    sec = trade['code']
    dt = trade['time']
    recorded = trade['price']

    # close[14:00]: 8 fields, no offset
    df_new = data_api._get_price_raw(
        sec, end_date=dt, count=1,
        fields=["open", "close", "high", "low", "high_limit", "low_limit", "paused", "volume"],
        frequency="1m", fq=None
    )
    if df_new.empty:
        new_close = None
    else:
        if isinstance(df_new.columns, pd.MultiIndex):
            row = df_new.xs(sec, axis=1, level=1).iloc[0]
        else:
            row = df_new.iloc[0]
        new_close = round(float(row.get('close', 0)), 2)

    # open[14:01]: 6 fields, +1min offset
    df_old = data_api._get_price_raw(
        sec, end_date=dt + pd.Timedelta(minutes=1), count=1,
        fields=["open", "close", "high_limit", "low_limit", "paused", "volume"],
        frequency="1m", fq=None
    )
    if df_old.empty:
        old_open = None
    else:
        if isinstance(df_old.columns, pd.MultiIndex):
            row = df_old.xs(sec, axis=1, level=1).iloc[0]
        else:
            row = df_old.iloc[0]
        old_open = round(float(row.get('open', 0)), 2)

    match_close = abs(recorded - (new_close or -999)) < 0.005
    match_open = abs(recorded - (old_open or -999)) < 0.005
    if match_close and match_open:
        verdict = 'BOTH (close==open)'
    elif match_close:
        verdict = 'CLOSE[14:00]'
    elif match_open:
        verdict = 'OPEN[14:01]'
    else:
        verdict = 'NEITHER'
    results.append({
        'time': dt,
        'code': sec,
        'recorded': recorded,
        'close_14h': new_close,
        'open_14h+1': old_open,
        'verdict': verdict,
    })

df = pd.DataFrame(results)
print('=== pre_fallback4 14:00 trades: price matches close[14:00] or open[14:01]? ===')
print(df.to_string())
print()

# Summary
print(f'=== Summary ===')
print(df['verdict'].value_counts().to_string())
