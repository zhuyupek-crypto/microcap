"""Test 601558 is_st determination on 2020-06-01."""
import sys
sys.path.insert(0, r'D:\Work Space\local_quant')
import pandas as pd
from engine.data_api import DataAPI

# Initialize with research mode
api = DataAPI(data_root=r'D:\Work Space\HData\data\processed', compatibility_mode='research')

# Force load stock_basic by calling get_all_securities once
_ = api.get_all_securities(['stock'], date='2020-06-01')

# Check 601558 in stock_basic
print("=" * 60)
print("601558.XSHG stock_basic info")
print("=" * 60)
sb = api._stock_basic
if '601558.XSHG' in sb.index:
    row = sb.loc['601558.XSHG']
    print(f"  display_name: {row.get('display_name')}")
    print(f"  start_date: {row.get('start_date')}")
    print(f"  end_date (delist): {row.get('end_date')}")
else:
    print("  601558.XSHG NOT in stock_basic!")

# Check get_all_securities on 2020-06-01
print(f"\n{'=' * 60}")
print("get_all_securities(['stock'], '2020-06-01')")
print("=" * 60)
secs = api.get_all_securities(['stock'], date='2020-06-01')
has_601558 = '601558.XSHG' in secs.index
print(f"  601558.XSHG in pool: {has_601558}")
if has_601558:
    print(f"  display_name: {secs.loc['601558.XSHG', 'display_name']}")
    print(f"  start_date: {secs.loc['601558.XSHG', 'start_date']}")
    print(f"  end_date: {secs.loc['601558.XSHG', 'end_date']}")

# Check is_st on multiple dates
print(f"\n{'=' * 60}")
print("is_st check for 601558.XSHG on various dates")
print("=" * 60)
test_dates = ['2020-04-01', '2020-05-01', '2020-05-13', '2020-05-20',
              '2020-06-01', '2020-06-09', '2020-06-22', '2020-07-01', '2020-07-02']
for d in test_dates:
    try:
        result = api.get_extras('is_st', ['601558.XSHG'], start_date=d, end_date=d)
        val = result['601558.XSHG'][0] if '601558.XSHG' in result else 'N/A'
        print(f"  {d}: is_st = {val}")
    except Exception as e:
        print(f"  {d}: ERROR: {e}")

# Check ST list for 601558
print(f"\n{'=' * 60}")
print("ST list membership for 601558")
print("=" * 60)
s_norm = '601558.SH'
print(f"  s_norm: {s_norm}")
print(f"  in _st_ever_set: {s_norm in api._st_ever_set}")
print(f"  in _st_date_ranges_by_code: {s_norm in api._st_date_ranges_by_code}")
if s_norm in api._st_date_ranges_by_code:
    ranges = api._st_date_ranges_by_code[s_norm]
    print(f"  date ranges: {ranges}")
print(f"  _st_last_date_by_code: {api._st_last_date_by_code.get(s_norm)}")

# Check _st_codes_by_date_str around 2020-06
print(f"\n{'=' * 60}")
print("_st_codes_by_date_str around 2020-05~06 (601558)")
print("=" * 60)
for d_str in ['20200430', '20200513', '20200520', '20200601', '20200609', '20200622']:
    codes = api._st_codes_by_date_str.get(d_str, set())
    has = '601558.SH' in codes
    print(f"  {d_str}: 601558.SH in st_today = {has}")
