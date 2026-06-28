"""Verify minute data high_limit."""
import os, sys, json, hashlib
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

HDATA = r"D:\Work Space\HData"
TARGETS = ["300417.XSHE", "301167.XSHE", "600493.XSHG", "300535.XSHE"]
DT = "2026-05-26"

# Check 1-minute data for high_limit
for sec in TARGETS:
    code_num = sec.split(".")[0]
    year = "2026"
    fp = os.path.join(HDATA, "data", "processed", "1m_stock", code_num, f"{year}.parquet")
    if not os.path.exists(fp):
        print(f"{sec}: 1m file not found: {fp}")
        continue
    try:
        cols = pq.read_schema(fp)
        print(f"{sec}: 1m columns: {[c.name for c in cols]}")
        table = pq.read_table(fp, columns=["code", "date", "close", "high_limit"])
        df = table.to_pandas()
        df["date_str"] = df["date"].astype(str).str[:10]
        day = df[df["date_str"] == DT.replace("-", "")]
        if len(day) > 0:
            print(f"  {DT} rows: {len(day)}")
            print(f"  close sample: {day['close'].head(3).tolist()}")
            print(f"  high_limit sample: {day['high_limit'].head(3).tolist()}")
            if len(day) > 0:
                last = day.iloc[-1]
                print(f"  Last bar: close={last['close']} high_limit={last['high_limit']}")
                print(f"  close < high_limit? {last['close'] < last['high_limit']}")
        else:
            print(f"  No data for {DT}")
    except Exception as e:
        print(f"{sec}: ERROR: {e}")

# Also check daily parquet for high_limit column
print("\n=== Daily parquet columns ===")
dp = os.path.join(HDATA, "data", "processed", "1d_stock", "2026.parquet")
cols = pq.read_schema(dp)
print(f"Daily columns: {[c.name for c in cols]}")
has_hl = any("high_limit" in c.name.lower() for c in cols)
print(f"Has high_limit column? {has_hl}")

# Check 1m schema for high_limit
print("\n=== 1m parquet columns ===")
for sec in TARGETS:
    cn = sec.split(".")[0]
    fp = os.path.join(HDATA, "data", "processed", "1m_stock", cn, f"2026.parquet")
    if os.path.exists(fp):
        cols = pq.read_schema(fp)
        has_hl = any("high_limit" in c.name.lower() for c in cols)
        print(f"{sec}: has high_limit? {has_hl} columns: {[c.name for c in cols]}")
        break
