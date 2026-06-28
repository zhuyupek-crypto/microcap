"""Focused data chain probe: compare 300665 05-18 vs 4 stocks 05-25."""
import os, sys, hashlib
from pathlib import Path

ROOT = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003f")
LQ = r"D:\Work Space\local_quant"
sys.path.insert(0, LQ)
os.environ["HDATA_ROOT"] = "D:\\Work Space\\HData"
os.environ["LOCAL_QUANT_HDATA_SOURCE"] = "legacy"

EXP = "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"
sp = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
with open(sp, "rb") as f:
    assert hashlib.sha256(f.read()).hexdigest().upper() == EXP

import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
from engine.core import Engine
import engine.data_api as eda
import pandas as pd

checks = [
    ("300665.XSHE", "2026-05-18"),
    ("300417.XSHE", "2026-05-25"),
    ("301167.XSHE", "2026-05-25"),
    ("600493.XSHG", "2026-05-25"),
    ("300535.XSHE", "2026-05-25"),
]

def norm(s): return s.replace(".XSHE",".SZ").replace(".XSHG",".SH")
def mcap(s):
    n = int(s.split(".")[0])
    return 1.20 if ".XSHE" in s and 300000 <= n < 400000 else 1.10

print("=" * 60)
print("CREATING ENGINE & RUNNING BACKTEST")
print("=" * 60)
code = open(sp, "r", encoding="utf-8").read()
engine = Engine(code, "2026-05-01", "2026-05-27", 1_000_000)
eq, trades, logs, met = engine.run()
print(f"Trades: {len(trades)}, Logs: {len(logs)}")

# Save trades
trades.to_csv(ROOT / "probe_trades.csv", index=False)

# Check for 300665 on 2026-05-19
t665 = trades[(trades["code"] == "300665.XSHE") & (trades["time"].astype(str).str[:10] == "2026-05-19")]
print(f"\n300665 trades 2026-05-19: {len(t665)}")
if len(t665) > 0:
    print(t665.to_string())

# Check for 4 stocks on 2026-05-26
for sec in ["300417.XSHE", "301167.XSHE", "600493.XSHG", "300535.XSHE"]:
    tt = trades[(trades["code"] == sec) & (trades["time"].astype(str).str[:10] == "2026-05-26")]
    if len(tt) > 0:
        print(f"\n{sec} 2026-05-26 trades: {len(tt)}")
        print(tt.to_string())

print("\n" + "=" * 60)
print("PROBING DATA CHAIN (ENGINE CONTEXT)")
print("=" * 60)

da = engine.data_api
ns = engine.namespace
gp_ns = ns.get("get_price")

# Simulate strategy get_price by carefully setting context dates
# Use previous_date context approach
ctx = engine.context

print("\n=== L3: Strategy get_price simulation ===")
for sec, dt in checks:
    prev_dt = pd.to_datetime(dt)
    try:
        # Use the namespace get_price - must respect avoid_future_data
        # The engine's current_dt must be >= requested end_date
        r = gp_ns(sec, end_date=prev_dt, frequency="daily",
                  fields=["close", "high_limit"], count=1)
        if r is not None and not r.empty:
            cv = float(r["close"].iloc[0]) if "close" in r.columns else None
            hv = float(r["high_limit"].iloc[0]) if "high_limit" in r.columns else None
            ge = cv is not None and hv is not None and cv >= hv
            print(f"  L3 {dt} {sec}: close={cv} high_limit={hv} ge={ge}")
        else:
            print(f"  L3 {dt} {sec}: EMPTY")
    except Exception as e:
        print(f"  L3 {dt} {sec}: {e}")

print("\n=== L2: DataAPI.get_price ===")
for sec, dt in checks:
    try:
        r = da.get_price(sec, end_date=pd.to_datetime(dt), frequency="daily",
                         fields=["close", "high_limit"], count=1, fq=None)
        if r is not None and not r.empty:
            cv = float(r["close"].iloc[0]) if "close" in r.columns else None
            hv = float(r["high_limit"].iloc[0]) if "high_limit" in r.columns else None
            print(f"  L2 {dt} {sec}: close={cv} high_limit={hv}")
        else:
            print(f"  L2 {dt} {sec}: EMPTY")
    except Exception as e:
        print(f"  L2 {dt} {sec}: {e}")

print("\n=== L2: DataAPI.get_price with fq='pre' ===")
for sec, dt in checks:
    try:
        r = da.get_price(sec, end_date=pd.to_datetime(dt), frequency="daily",
                         fields=["close", "high_limit"], count=1, fq='pre')
        if r is not None and not r.empty:
            cv = float(r["close"].iloc[0]) if "close" in r.columns else None
            hv = float(r["high_limit"].iloc[0]) if "high_limit" in r.columns else None
            print(f"  L2_pre {dt} {sec}: close={cv} high_limit={hv}")
        else:
            print(f"  L2_pre {dt} {sec}: EMPTY")
    except Exception as e:
        print(f"  L2_pre {dt} {sec}: {e}")

print("\n=== L1: hdata_reader.history ===")
hdr = getattr(eda, "hdata_reader", None)
if hdr:
    for sec, dt in checks:
        hc = norm(sec)
        try:
            r = hdr.history([hc], "2026-05-01", "2026-05-27", ["close", "high_limit"], fq=None)
            if r is not None and not r.empty:
                hdt_num = int(dt.replace("-",""))
                if hdt_num in r.index:
                    row = r.loc[hdt_num]
                    cv = float(row.get(("close", hc), "N/A"))
                    hv = float(row.get(("high_limit", hc), "N/A"))
                    print(f"  HDR {dt} {sec}: close={cv} high_limit={hv}")
                else:
                    print(f"  HDR {dt} {sec}: date {hdt_num} not in index")
            else:
                print(f"  HDR {dt} {sec}: empty, columns={r.columns.tolist() if hasattr(r,'columns') else 'N/A'}")
        except Exception as e:
            print(f"  HDR {dt} {sec}: {e}")
else:
    print("  hdata_reader not found")

print("\n=== L0: Raw HData (post-engine, pyarrow) ===")
import pyarrow.parquet as pq
h0f = os.path.join(os.environ["HDATA_ROOT"], "data", "processed", "1d_stock", "2026.parquet")
h0 = pq.read_table(h0f, columns=["code","date","close","pre_close","adj_factor"]).to_pandas()
h0["code"] = h0["code"].astype(str)
h0["ds"] = h0["date"].astype(str)

for sec, dt in checks:
    hc = norm(sec)
    hdt = dt.replace("-","")
    r = h0[(h0["code"]==hc) & (h0["ds"]==hdt)]
    if len(r) > 0:
        rr = r.iloc[0]
        pc = float(rr["pre_close"])
        hl = round(pc * mcap(sec) / 0.01) * 0.01
        print(f"  L0 {dt} {sec}: close={rr['close']:.2f} pre_close={pc:.2f} correct_hl={hl:.2f}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Trades: {len(trades)}")
print(f"300665 sell on 2026-05-19: {'YES' if len(t665) > 0 else 'NO'}")
if len(t665) > 0:
    print(f"  300665 sold {int(t665.iloc[0]['amount'])} @ {t665.iloc[0]['price']}")
