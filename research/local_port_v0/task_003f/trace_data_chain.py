"""Trace data chain L0→L3 for 4 target stocks on 2026-05-25 and 2026-05-26."""
import os, sys, json, hashlib
from pathlib import Path

ROOT = r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003f"
OUT = Path(ROOT)
OUT.mkdir(parents=True, exist_ok=True)

import pandas as pd
import numpy as np
import pyarrow.parquet as pq

# Verify strategy SHA
EXPECTED = "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"
fp = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
with open(fp, "rb") as f:
    actual = hashlib.sha256(f.read()).hexdigest().upper()
assert actual == EXPECTED, f"SHA mismatch: {actual[:16]}"
print(f"[OK] Strategy SHA: {actual[:16]}...")

# Target stocks
TARGETS = ["300417.XSHE", "301167.XSHE", "600493.XSHG", "300535.XSHE"]
DATES = ["2026-05-25", "2026-05-26"]
HDATA = r"D:\Work Space\HData"

def norm(sec):
    return sec.replace(".XSHE", ".SZ").replace(".XSHG", ".SH")

# ============================================================
# L0: Raw HData parquet
# ============================================================
print("\n=== L0: Raw HData parquet ===")
h0_file = os.path.join(HDATA, "data", "processed", "1d_stock", "2026.parquet")
with open(h0_file, "rb") as f:
    h0_sha = hashlib.sha256(f.read()).hexdigest().upper()

table = pq.read_table(h0_file, columns=["code","date","open","high","low","close","pre_close","pct_chg","vol","amount","adj_factor"])
h0 = table.to_pandas()
h0["code"] = h0["code"].astype(str)
h0["date_str"] = h0["date"].astype(str)

l0_rows = []
for sec in TARGETS:
    hc = norm(sec)
    for dt in DATES:
        hdt = dt.replace("-", "")
        r = h0[(h0["code"] == hc) & (h0["date_str"] == hdt)]
        if len(r) > 0:
            rr = r.iloc[0]
            pc = float(rr["pre_close"])
            board = "SZ" if ".XSHE" in sec else "SH"
            mult = 1.20 if (board == "SZ" and 300000 <= int(sec.split(".")[0]) < 400000) else 1.10
            hl = round(pc * mult / 0.01) * 0.01
            ll = round(pc * (2 - mult) / 0.01) * 0.01
            l0_rows.append({
                "layer": "L0_raw_hdata", "security": sec, "date": dt,
                "file": h0_file, "file_sha256": h0_sha[:16],
                "open": float(rr["open"]), "high": float(rr["high"]), "low": float(rr["low"]),
                "close": float(rr["close"]), "pre_close": pc, "pct_chg": float(rr["pct_chg"]),
                "adj_factor": float(rr["adj_factor"]), "high_limit": hl, "low_limit": ll,
                "close_ge_high_limit": float(rr["close"]) >= hl,
                "low_le_low_limit": float(rr["low"]) <= ll,
                "vol": float(rr["vol"]), "amount": float(rr["amount"]),
            })
            print(f"  L0 {dt} {sec}: C={rr['close']:.2f} HL={hl:.2f} AtHL={float(rr['close']) >= hl} ADJ={rr['adj_factor']:.6f}")

# ============================================================
# L1: DataAPI._get_price_raw
# ============================================================
print("\n=== L1: DataAPI._get_price_raw ===")
sys.path.insert(0, r"D:\Work Space\local_quant")
os.environ["LOCAL_QUANT_HDATA_SOURCE"] = "legacy"
from engine.data_api import DataAPI

api = DataAPI(data_root=HDATA)
l1_rows = []
for sec in TARGETS:
    for dt in DATES:
        try:
            raw = api._get_price_raw(sec, end_date=pd.to_datetime(dt), frequency="daily",
                                     fields=["close", "high_limit"], count=1, fq=None)
            close_val = float(raw["close"].iloc[0]) if raw is not None and not raw.empty else None
            hl_val = float(raw["high_limit"].iloc[0]) if raw is not None and not raw.empty else None
            idx = str(raw.index[0])[:10] if raw is not None and not raw.empty else None
            l1_rows.append({
                "layer": "L1_dataapi_raw", "security": sec, "date": dt,
                "return_index": idx, "close": close_val, "high_limit": hl_val,
                "param_end_date": dt, "param_fq": None, "param_count": 1,
            })
            print(f"  L1 {dt} {sec}: idx={idx} C={close_val} HL={hl_val}")
        except Exception as e:
            print(f"  L1 ERROR {dt} {sec}: {e}")

# ============================================================
# L2: Engine's wrapped get_price (namespace level)
# ============================================================
print("\n=== L2: Engine wrapped get_price ===")
import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
from engine.core import Engine

l2_rows = []
# Use a minimal strategy to access the namespace
code = """
from jqdata import *
def initialize(c):
    run_daily(trade, "09:30")
def trade(c):
    pass
"""
eng = Engine(code, "2026-05-01", "2026-05-27", 1000000)
ns = eng.namespace
wrap_get_price = ns.get("get_price")
if wrap_get_price:
    for sec in TARGETS:
        for dt in DATES:
            prev_dt = pd.to_datetime(dt)
            try:
                result = wrap_get_price(sec, end_date=prev_dt, frequency="daily",
                                        fields=["close", "high_limit"], count=1)
                if result is not None and not result.empty:
                    close_val = float(result["close"].iloc[0])
                    hl_val = float(result["high_limit"].iloc[0])
                    idx = str(result.index[0])[:10]
                    l2_rows.append({
                        "layer": "L2_wrapped_gp", "security": sec, "date": dt,
                        "return_index": idx, "close": close_val, "high_limit": hl_val,
                        "close_ge_high_limit": close_val >= hl_val,
                    })
                    print(f"  L2 {dt} {sec}: idx={idx} C={close_val} HL={hl_val} AtHL={close_val >= hl_val}")
                else:
                    print(f"  L2 {dt} {sec}: empty result")
            except Exception as e:
                print(f"  L2 ERROR {dt} {sec}: {e}")
else:
    print("  get_price not found in namespace")

# ============================================================
# L3: Strategy call simulation
# ============================================================
print("\n=== L3: Strategy get_price (prepare_stock_list simulation) ===")
l3_rows = []
for sec in TARGETS:
    for dt in DATES:
        prev_dt = pd.to_datetime(dt)
        try:
            result = wrap_get_price(sec, end_date=prev_dt, frequency="daily",
                                    fields=["close", "high_limit"], count=1)
            if result is not None and not result.empty:
                close_val = float(result["close"].iloc[0])
                hl_val = float(result["high_limit"].iloc[0])
                in_hl = close_val >= hl_val
                l3_rows.append({
                    "layer": "L3_strategy_gp", "security": sec, "date": dt,
                    "close": close_val, "high_limit": hl_val,
                    "close_ge_high_limit": in_hl,
                    "in_yesterday_HL_list": in_hl,
                })
                print(f"  L3 {dt} {sec}: C={close_val} HL={hl_val} AtHL={in_hl} InHL={in_hl}")
        except Exception as e:
            print(f"  L3 ERROR {dt} {sec}: {e}")

# ============================================================
# Combine and output
# ============================================================
all_rows = l0_rows + l1_rows + l2_rows + l3_rows
df = pd.DataFrame(all_rows)
df.to_csv(OUT / "local_data_lineage_0526.csv", index=False)
print(f"\n[OK] local_data_lineage_0526.csv: {len(df)} rows")

# Summary comparison
print("\n=== L0 vs L3 comparison ===")
for sec in TARGETS:
    for dt in DATES:
        l0_close = None; l3_close = None; l0_hl = None; l3_hl = None
        for r in l0_rows:
            if r["security"] == sec and r["date"] == dt:
                l0_close = r["close"]; l0_hl = r["high_limit"]
        for r in l3_rows:
            if r["security"] == sec and r["date"] == dt:
                l3_close = r["close"]; l3_hl = r["high_limit"]
        same = (l0_close == l3_close) and (l0_hl == l3_hl)
        print(f"  {dt} {sec}: L0 C={l0_close} HL={l0_hl} | L3 C={l3_close} HL={l3_hl} | {'MATCH' if same else 'DIFFER'}")
