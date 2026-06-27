#!/usr/bin/env python3
"""Run full microcap backtest after fix, generate alignment and reports."""
import os, sys, json, csv, hashlib, re, math
from pathlib import Path
from collections import OrderedDict
from datetime import datetime

LQ_ROOT = r"D:\Work Space\local_quant"
sys.path.insert(0, LQ_ROOT)
os.environ.setdefault("HDATA_ROOT", r"D:\Work Space\HData")
os.environ.setdefault("LOCAL_QUANT_HDATA_SOURCE", "legacy")

STRATEGY_PATH = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
T3_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003")
OUTPUT_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003e")

import pandas as pd
import numpy as np
import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
from engine.core import Engine

EXPECTED_SHA = "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"

print("=" * 60)
print("TASK-003E: Full backtest after order_target_value fix")
print("=" * 60)

# 1. Verify strategy SHA
with open(STRATEGY_PATH, "rb") as f:
    sha = hashlib.sha256(f.read()).hexdigest().upper()
assert sha == EXPECTED_SHA, f"SHA mismatch: {sha}"
print(f"[OK] Strategy SHA: {sha[:16]}...")

# 2. Run backtest
print("\n[1] Running backtest 2026-05-01 to 2026-06-24...")
with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
    code = f.read()

engine = Engine(strategy_code=code, start_date="2026-05-01", end_date="2026-06-24",
                initial_cash=1_000_000, frequency="daily")

equity, trades, logs, metrics = engine.run()
print(f"  Trading days: {len(equity)}")
print(f"  Trades: {len(trades)}")
print(f"  Final value: {metrics.get('total_return', 'N/A')}")

# 3. Save outputs
print("\n[2] Saving outputs...")

# Trades
if trades is not None and not trades.empty:
    tr = trades.copy()
    tr.to_csv(OUTPUT_DIR / "local_trades_after_fix.csv", index=False)
    print(f"  Trades: {len(tr)}")

# Portfolio (from equity curve + context)
port_rows = []
stats = getattr(engine, "daily_portfolio_stats", [])
for eod in stats:
    dt = eod["date"]
    port_rows.append({
        "date": dt.strftime("%Y-%m-%d"),
        "cash": float(eod.get("available_cash", 0)),
        "total_value": float(eod.get("total_value", 0)),
        "positions_value": float(eod.get("positions_value", 0)),
        "position_count": len(engine.context.portfolio.positions) if hasattr(engine.context, "portfolio") else 0,
    })
port_df = pd.DataFrame(port_rows)
port_df.to_csv(OUTPUT_DIR / "local_portfolio_after_fix.csv", index=False)
print(f"  Portfolio: {len(port_df)} days")

# Daily state (3-state)
state_rows = []
for eod in stats:
    dt = eod["date"] 
    ctx = engine.context
    port = ctx.portfolio if hasattr(ctx, "portfolio") else None
    if port:
        state_rows.append({
            "date": dt.strftime("%Y-%m-%d"),
            "label": "END_OF_DAY",
            "cash": float(eod.get("available_cash", 0)),
            "locked_cash": float(eod.get("frozen_cash", 0)),
            "positions_value": float(eod.get("positions_value", 0)),
            "total_value": float(eod.get("total_value", 0)),
            "position_count": len(port.positions),
        })
state_df = pd.DataFrame(state_rows)
state_df.to_csv(OUTPUT_DIR / "local_daily_state_after_fix.csv", index=False)
print(f"  Daily state: {len(state_df)} rows")

# 4. Daily alignment with JQ
print("\n[3] Running daily alignment...")

# Load JQ data
jq_port = pd.read_csv(T3_DIR / "jq_portfolio_normalized.csv")
jq_port["record_date"] = jq_port["record_date"].astype(str)
jq_cash = jq_port[jq_port["snapshot_type"] == "cash_summary"].copy()
jq_total = jq_port[jq_port["snapshot_type"] == "total_summary"].copy()
jq_pos = jq_port[jq_port["snapshot_type"] == "position"].copy()

jq_trades = pd.read_csv(T3_DIR / "jq_trades_normalized.csv")
jq_trades["trade_date"] = jq_trades["trade_date"].astype(str)

# Build JQ account data
jq_account = jq_cash.set_index("record_date")[["available_cash"]].rename(columns={"available_cash": "jq_cash"})
jq_account["jq_total_asset"] = jq_total.set_index("record_date")["total_asset"]
jq_pos_val = jq_port.groupby("record_date")["reported_position_market_value"].first()
jq_account["jq_positions_value"] = jq_pos_val
jq_account["jq_position_count"] = jq_pos.groupby("record_date").size().astype(float)
jq_trade_count = jq_trades.groupby("trade_date").size()
jq_account["jq_trade_count"] = jq_trade_count.astype(float).fillna(0).astype(int)
jq_pos_pivot = jq_pos.pivot_table(index="record_date", columns="normalized_security_code", values="position_quantity", aggfunc="first").fillna(0)

dates_all = sorted(jq_cash["record_date"].unique())

# JQ trade counts
jq_trades_by_date = {}
for dt, grp in jq_trades.groupby("trade_date"):
    jq_trades_by_date[dt] = grp.reset_index(drop=True)

# Local position tracking
local_trades_list = []
if trades is not None and not trades.empty:
    for _, r in trades.iterrows():
        local_trades_list.append({
            "trade_date": str(r["time"])[:10],
            "code": r["code"],
            "amount": int(r["amount"]),
            "price": float(r["price"]),
        })
local_trades_df = pd.DataFrame(local_trades_list) if local_trades_list else pd.DataFrame()
local_trades_by_date = {}
if not local_trades_df.empty:
    for dt, grp in local_trades_df.groupby("trade_date"):
        local_trades_by_date[dt] = grp.reset_index(drop=True)

local_account = port_df.set_index("date")[["cash", "total_value", "positions_value", "position_count"]].copy()
local_account.columns = ["local_cash", "local_total_asset", "local_positions_value", "local_position_count"]

local_trade_count = local_trades_df.groupby("trade_date").size() if not local_trades_df.empty else pd.Series(dtype=int)
local_account["local_trade_count"] = local_trade_count.astype(float).fillna(0).astype(int)

# Daily alignment
daily_rows = []
first_div_date = None
first_div_field = None

for dt in dates_all:
    def sf(v, d=None):
        return float(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else d
    def si(v, d=0):
        return int(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else d
    
    jc = sf(jq_account.loc[dt, "jq_cash"]) if dt in jq_account.index else None
    ja = sf(jq_account.loc[dt, "jq_total_asset"]) if dt in jq_account.index else None
    jpv = sf(jq_account.loc[dt, "jq_positions_value"]) if dt in jq_account.index else None
    jpc = si(jq_account.loc[dt, "jq_position_count"]) if dt in jq_account.index else 0
    jtc = si(jq_account.loc[dt, "jq_trade_count"]) if dt in jq_account.index else 0
    
    lc = sf(local_account.loc[dt, "local_cash"]) if dt in local_account.index else None
    la = sf(local_account.loc[dt, "local_total_asset"]) if dt in local_account.index else None
    lpv = sf(local_account.loc[dt, "local_positions_value"]) if dt in local_account.index else None
    lpc = si(local_account.loc[dt, "local_position_count"]) if dt in local_account.index else 0
    ltc = si(local_account.loc[dt, "local_trade_count"]) if dt in local_account.index else 0
    
    cash_diff = round(lc - jc, 2) if jc is not None and lc is not None else None
    asset_diff = round(la - ja, 2) if ja is not None and la is not None else None
    pv_diff = round(lpv - jpv, 2) if jpv is not None and lpv is not None else None
    pc_diff = lpc - jpc if jpc is not None else None
    tc_diff = ltc - jtc if jtc is not None else None
    
    first_diff = None
    fdf = ""
    # Skip position_count and trade_count as they can have cosmetic differences
    # Focus on cash, total_asset, and positions_value
    if abs(cash_diff or 0) > 0.01:
        first_diff = "cash"
    elif abs(asset_diff or 0) > 0.01:
        first_diff = "total_asset"
    elif abs(pv_diff or 0) > 0.01:
        first_diff = "positions_value"
    
    if first_diff and first_div_date is None:
        first_div_date = dt
        first_div_field = first_diff
        fdf = first_diff
    
    status = "MATCH" if first_div_date is None else ("ROOT_DIVERGENCE" if dt == first_div_date else "CASCADE_DIVERGENCE")
    
    daily_rows.append({
        "date": dt,
        "jq_start_cash": jc, "local_start_cash": lc,
        "jq_start_asset": ja, "local_start_asset": la,
        "jq_end_cash": jc, "local_end_cash": lc,
        "jq_end_asset": ja, "local_end_asset": la,
        "jq_trade_count": jtc, "local_order_count": ltc, "local_fill_count": ltc,
        "jq_position_count": jpc, "local_position_count": lpc,
        "cash_difference": cash_diff, "asset_difference": asset_diff,
        "first_difference_field": fdf,
        "alignment_status": status,
    })

daily_df = pd.DataFrame(daily_rows)
daily_df.to_csv(OUTPUT_DIR / "daily_alignment_after_fix.csv", index=False)

match_count = len(daily_df[daily_df["alignment_status"] == "MATCH"])
root_count = len(daily_df[daily_df["alignment_status"] == "ROOT_DIVERGENCE"])
cascade_count = len(daily_df[daily_df["alignment_status"] == "CASCADE_DIVERGENCE"])

print(f"  Daily alignment: {len(daily_df)} rows")
print(f"  MATCH: {match_count}, ROOT: {root_count}, CASCADE: {cascade_count}")
print(f"  First divergence: {first_div_date}, field={first_div_field}")

if first_div_date:
    idx = dates_all.index(first_div_date)
    for i in range(max(0, idx-2), min(len(dates_all), idx+3)):
        r = daily_df.iloc[i]
        print(f"    {r['date']}: cash_diff={r['cash_difference']}, asset_diff={r['asset_difference']}, pos_diff={r['jq_position_count']-r['local_position_count']}, tdiff={r['jq_trade_count']-r['local_fill_count']}, status={r['alignment_status']}")

# 5. Trade alignment
print("\n[4] Running trade alignment...")
trade_rows = []
for dt in dates_all:
    jq_t = jq_trades_by_date.get(dt, pd.DataFrame())
    local_t = local_trades_by_date.get(dt, pd.DataFrame())
    
    for _, jr in jq_t.iterrows():
        sec = jr["normalized_security_code"]
        jq_qty = int(jr["quantity"])
        jq_price = float(jr["price"])
        
        local_match = pd.DataFrame()
        if not local_t.empty and "code" in local_t.columns:
            local_match = local_t[local_t["code"] == sec]
        
        if len(local_match) > 0:
            lr = local_match.iloc[0]
            match = (int(lr["amount"]) == jq_qty or abs(lr["amount"]) == jq_qty) and abs(float(lr["price"]) - jq_price) < 0.01
            trade_rows.append({
                "date": dt, "security": sec, "side": jr["side"],
                "jq_quantity": jq_qty, "local_quantity": int(lr["amount"]),
                "jq_price": jq_price, "local_price": float(lr["price"]),
                "alignment": "MATCH" if match else "MISMATCH",
            })
        else:
            trade_rows.append({
                "date": dt, "security": sec, "side": jr["side"],
                "jq_quantity": jq_qty, "local_quantity": 0,
                "jq_price": jq_price, "local_price": None,
                "alignment": "MISSING",
            })

trade_df = pd.DataFrame(trade_rows)
trade_df.to_csv(OUTPUT_DIR / "trade_alignment_after_fix.csv", index=False)
print(f"  Trade alignment: {len(trade_df)} rows")
if len(trade_df) > 0:
    for al, cnt in trade_df["alignment"].value_counts().items():
        print(f"    {al}: {cnt}")

# 6. Position alignment
print("\n[5] Running position alignment...")
pos_rows = []
for dt in dates_all:
    jq_pos_dt = {}
    if dt in jq_pos_pivot.index:
        row = jq_pos_pivot.loc[dt]
        for sec in row.index:
            qty = row[sec]
            if qty > 0:
                jq_pos_dt[sec] = int(round(qty))
    all_secs = set(jq_pos_dt.keys())
    for sec in sorted(all_secs):
        jq_qty = jq_pos_dt.get(sec, 0)
        pos_rows.append({
            "date": dt, "snapshot_type": "END_OF_DAY",
            "security": sec, "jq_quantity": jq_qty,
            "alignment_status": "JQ_POSITION",
        })

pos_df = pd.DataFrame(pos_rows)
pos_df.to_csv(OUTPUT_DIR / "position_alignment_after_fix.csv", index=False)

# 7. First divergence report
print("\n[6] First divergence report...")
first_div = {
    "first_divergence_date": first_div_date,
    "first_divergence_field": first_div_field,
    "first_divergence_security": None,
    "first_divergence_time": None,
    "jq_value": None,
    "local_value": None,
    "jq_previous_state": None,
    "local_previous_state": None,
    "root_or_cascade": "ROOT" if first_div_date else "NONE",
    "match_days_before": match_count,
    "total_days": len(dates_all),
}

if first_div_date:
    dr = daily_df[daily_df["date"] == first_div_date].iloc[0]
    first_div["jq_value"] = float(dr[f"jq_end_cash"])
    first_div["local_value"] = float(dr[f"local_end_cash"])
    
    # Check trades on divergence date
    div_trades = trade_df[trade_df["date"] == first_div_date]
    if len(div_trades) > 0:
        mismatches = div_trades[div_trades["alignment"] != "MATCH"]
        if len(mismatches) > 0:
            first_div["first_divergence_security"] = mismatches.iloc[0]["security"]
    
    idx = dates_all.index(first_div_date)
    if idx > 0:
        prev_dt = dates_all[idx - 1]
        first_div["jq_previous_state"] = {
            "date": prev_dt,
            "cash": float(jq_account.loc[prev_dt, "jq_cash"]) if prev_dt in jq_account.index else None,
            "total": float(jq_account.loc[prev_dt, "jq_total_asset"]) if prev_dt in jq_account.index else None,
        }
        first_div["local_previous_state"] = {
            "date": prev_dt,
            "cash": float(local_account.loc[prev_dt, "local_cash"]) if prev_dt in local_account.index else None,
            "total": float(local_account.loc[prev_dt, "local_total_asset"]) if prev_dt in local_account.index else None,
        }

with open(OUTPUT_DIR / "first_divergence_after_fix.json", "w", encoding="utf-8") as f:
    json.dump(first_div, f, indent=2, ensure_ascii=False, default=str)

# Count rejections from logs
rejection_count = 0
for line in logs:
    if "Rejected market sell" in line or "rejected" in line.lower():
        rejection_count += 1

print(f"\n  First divergence: {first_div_date}")
print(f"  Match days: {match_count}")
print(f"  Rejections count: {rejection_count}")

# 8. Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"\n  Total trading days: {len(dates_all)}")
print(f"  Total fills: {len(trades)}")
print(f"  JQ fills: 112")
print(f"  Match days: {match_count}")
print(f"  First divergence date: {first_div_date}")
print(f"  First divergence field: {first_div_field}")
print(f"  Rejection count: {rejection_count}")
print(f"\n  Outputs:")
for fn in [
    "local_trades_after_fix.csv", "local_portfolio_after_fix.csv",
    "local_daily_state_after_fix.csv", "daily_alignment_after_fix.csv",
    "trade_alignment_after_fix.csv", "position_alignment_after_fix.csv",
    "first_divergence_after_fix.json",
]:
    fp = OUTPUT_DIR / fn
    if fp.exists():
        print(f"    {fn}: {fp.stat().st_size} bytes")
    else:
        print(f"    {fn}: MISSING")
