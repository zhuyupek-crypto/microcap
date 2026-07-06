"""Trace _get_price_impl to see if -1min offset is applied and what _history_cached returns.

 Monkey-patch _history_cached to log its end_date parameter and return value.
"""
import os
import sys
import pandas as pd

os.environ.setdefault('LOCAL_QUANT_COMPATIBILITY_MODE', 'research')
os.environ.setdefault('HDATA_ROOT', r'D:\Work Space\HData')
sys.path.insert(0, r'D:\Work Space\local_quant')

from engine.data_api import DataAPI

data_api = DataAPI(compatibility_mode='research')

# Monkey-patch _history_cached to trace calls
orig_history_cached = data_api._history_cached
def traced_history_cached(*args, **kwargs):
    end_date = kwargs.get('end_date')
    unit = kwargs.get('unit')
    field = kwargs.get('field')
    count = kwargs.get('count')
    print(f'  [_history_cached] unit={unit}, field={field}, count={count}, end_date={end_date}')
    result = orig_history_cached(*args, **kwargs)
    if result is not None and not result.empty:
        print(f'  [_history_cached] returned index: {list(result.index)}')
        if hasattr(result, 'columns'):
            print(f'  [_history_cached] columns: {list(result.columns)}')
    else:
        print(f'  [_history_cached] returned EMPTY')
    return result

data_api._history_cached = traced_history_cached

security = '603991.XSHG'
current_dt = pd.Timestamp('2020-03-13 14:00:00')

print('=== OLD code path: 6 fields, end=14:01 ===')
print(f'Calling _get_price_raw(security, end_date=14:01, fields=6, frequency=1m)')
df_old = data_api._get_price_raw(
    security, end_date=current_dt + pd.Timedelta(minutes=1), count=1,
    fields=["open", "close", "high_limit", "low_limit", "paused", "volume"],
    frequency="1m", fq=None
)
print(f'Result index: {df_old.index[0] if not df_old.empty else "EMPTY"}')
if not df_old.empty:
    if isinstance(df_old.columns, pd.MultiIndex):
        row = df_old.xs(security, axis=1, level=1).iloc[0]
    else:
        row = df_old.iloc[0]
    print(f'open={row.get("open")}, close={row.get("close")}')

print()
print('=== NEW code path: 8 fields, end=14:00 ===')
print(f'Calling _get_price_raw(security, end_date=14:00, fields=8, frequency=1m)')
df_new = data_api._get_price_raw(
    security, end_date=current_dt, count=1,
    fields=["open", "close", "high", "low", "high_limit", "low_limit", "paused", "volume"],
    frequency="1m", fq=None
)
print(f'Result index: {df_new.index[0] if not df_new.empty else "EMPTY"}')
if not df_new.empty:
    if isinstance(df_new.columns, pd.MultiIndex):
        row = df_new.xs(security, axis=1, level=1).iloc[0]
    else:
        row = df_new.iloc[0]
    print(f'open={row.get("open")}, close={row.get("close")}')
