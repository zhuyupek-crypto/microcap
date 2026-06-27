#!/usr/bin/env python3
"""
TASK-MICROCAP-003C: 逐日执行对齐与首个可观测分叉定位
"""
import pandas as pd
import numpy as np
import json, csv, os, sys, re, math
from pathlib import Path
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta

OUTPUT_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003")

# ============================================================
# 1. LOAD DATA
# ============================================================
print("=" * 60)
print("TASK-MICROCAP-003C: 逐日执行对齐与分叉定位")
print("=" * 60)

print("\n[1] Loading data...")

jq_trades = pd.read_csv(OUTPUT_DIR / "jq_trades_normalized.csv")
jq_trades["trade_date"] = jq_trades["trade_date"].astype(str)
jq_trades = jq_trades.sort_values(["trade_date", "source_sequence"]).reset_index(drop=True)
print(f"  JQ trades: {len(jq_trades)}")

jq_port = pd.read_csv(OUTPUT_DIR / "jq_portfolio_normalized.csv")
jq_port["record_date"] = jq_port["record_date"].astype(str)
print(f"  JQ portfolio rows: {len(jq_port)}")

jq_cash = jq_port[jq_port["snapshot_type"] == "cash_summary"].copy()
jq_total = jq_port[jq_port["snapshot_type"] == "total_summary"].copy()
jq_pos = jq_port[jq_port["snapshot_type"] == "position"].copy()
print(f"  JQ cash_summary: {len(jq_cash)}, total_summary: {len(jq_total)}, position: {len(jq_pos)}")

local_trades = pd.read_csv(OUTPUT_DIR / "local_trades_normalized.csv")
local_trades["trade_date"] = local_trades["trade_date"].astype(str)
local_trades = local_trades.sort_values("trade_date").reset_index(drop=True)
local_trades["side"] = local_trades.apply(lambda r: "sell" if r["amount"] < 0 else "buy", axis=1)
local_trades["abs_amount"] = local_trades["amount"].abs()
print(f"  Local trades: {len(local_trades)} (buys={len(local_trades[local_trades['side']=='buy'])}, sells={len(local_trades[local_trades['side']=='sell'])})")

local_port = pd.read_csv(OUTPUT_DIR / "local_portfolio_normalized.csv")
local_port["date"] = local_port["date"].astype(str)
print(f"  Local portfolio: {len(local_port)}")

local_state = pd.read_csv(OUTPUT_DIR / "local_daily_state.csv")
local_state["date"] = local_state["date"].astype(str)
print(f"  Local state rows: {len(local_state)}")

dates_all = sorted(jq_cash["record_date"].unique())
print(f"  Trading dates: {len(dates_all)} from {dates_all[0]} to {dates_all[-1]}")

# ============================================================
# 2. JQ ACCOUNT-LEVEL DATA
# ============================================================
print("\n[2] Building JQ account-level data...")

jq_account = jq_cash.set_index("record_date")[["available_cash"]].rename(columns={"available_cash": "jq_cash"})
jq_account["jq_total_asset"] = jq_total.set_index("record_date")["total_asset"]
jq_pos_val = jq_port.groupby("record_date")["reported_position_market_value"].first()
jq_account["jq_positions_value"] = jq_pos_val
jq_account["jq_position_count"] = jq_pos.groupby("record_date").size()
jq_pos_pivot = jq_pos.pivot_table(index="record_date", columns="normalized_security_code", values="position_quantity", aggfunc="first").fillna(0)
jq_trade_count = jq_trades.groupby("trade_date").size()
jq_account["jq_trade_count"] = jq_trade_count.astype(float).fillna(0).astype(int)
print(f"  {len(jq_account)} dates")

# ============================================================
# 3. ENGINE LOGS PARSING
# ============================================================
print("\n[3] Parsing engine logs...")
with open(OUTPUT_DIR / "local_engine_logs.txt", "r", encoding="utf-8") as f:
    log_lines = f.readlines()
print(f"  {len(log_lines)} log lines")

# Build position tracker from order execution lines
local_positions = {}
running = {}
for line in log_lines:
    m = re.match(r'\[(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}\]\s+INFO:\s+Order \d+ matched/executed: filled (-?\d+) of (\S+) at ([\d.]+)', line)
    if m:
        dt = m.group(1)
        qty = int(m.group(2))
        sec = m.group(3)
        running[sec] = running.get(sec, 0) + qty
        local_positions[dt] = {k: v for k, v in running.items() if v != 0}

# Backward fill positions for dates without trades
for dt in dates_all:
    if dt not in local_positions:
        prev_idx = dates_all.index(dt) - 1
        while prev_idx >= 0:
            prev_dt = dates_all[prev_idx]
            if prev_dt in local_positions:
                local_positions[dt] = dict(local_positions[prev_dt])
                break
            prev_idx -= 1
        if dt not in local_positions:
            local_positions[dt] = {}
print(f"  Position data for {len(local_positions)} dates")

# Parse rejection logs
rejection_logs = {}
for line in log_lines:
    m = re.match(r'\[(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\]\s+INFO:\s+Rejected market sell for (\S+) due to (.+)', line)
    if m:
        dt, tm, sec, reason = m.groups()
        rejection_logs.setdefault(dt, []).append({"time": tm, "security": sec, "reason": reason.strip(), "line": line.strip()})

# Parse order intent from buy/sell plans
order_intents = {}
for line in log_lines:
    m = re.match(r'\[(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}\]\s+INFO:\s+(sell|buy)_plan_0930:\s*(.*)', line)
    if m:
        dt, ptype, content = m.groups()
        content = content.strip()
        if content.lower() == "empty":
            order_intents.setdefault(dt, {})[ptype] = []
        else:
            items = []
            for part in content.split(";"):
                part = part.strip()
                if part:
                    try:
                        s, v = part.split(":")
                        items.append({"security": s, "target_value": float(v)})
                    except:
                        pass
            order_intents.setdefault(dt, {})[ptype] = items

print(f"  Rejection dates: {len(rejection_logs)}")
print(f"  Order intent dates: {len(order_intents)}")

# ============================================================
# 4. LOCAL ACCOUNT-LEVEL DATA
# ============================================================
print("\n[4] Building local account-level data...")

local_account = local_port.set_index("date")[["cash", "total_value", "positions_value"]].copy()
local_account.columns = ["local_cash", "local_total_asset", "local_positions_value"]
local_account["local_position_count"] = [len(local_positions.get(dt, {})) for dt in local_account.index]
local_account["local_trade_count"] = local_trades.groupby("trade_date").size().astype(float).fillna(0).astype(int)
print(f"  {len(local_account)} dates")

# ============================================================
# 5. PRE-DIVERGENCE VALIDATION
# ============================================================
print("\n[5] Pre-divergence validation (days 1-22)...")

pre_div_dates = dates_all[:22]
field_groups = OrderedDict([
    ("cash", "账户现金"),
    ("total_asset", "账户总资产"),
    ("positions_value", "持仓市值"),
    ("position_count", "持仓数量"),
])

def safe_float(v, default=None):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return default
    return float(v)

def safe_int(v, default=0):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return default
    return int(v)

pre_div_rows = []
for dt in pre_div_dates:
    for fk, fl in field_groups.items():
        col_jq = f"jq_{fk}"
        col_local = f"local_{fk}"
        jq_v = safe_float(jq_account.loc[dt, col_jq]) if dt in jq_account.index else None
        local_v = safe_float(local_account.loc[dt, col_local]) if dt in local_account.index else None
        if jq_v is None or local_v is None:
            continue
        if fk == "position_count":
            jq_v = int(jq_v)
            local_v = int(local_v)
        diff = local_v - jq_v
        tol = 0.01 if abs(diff) >= 0.01 else 0.0
        is_eq = abs(diff) < 0.01 if fk != "position_count" else (jq_v == local_v)
        pre_div_rows.append({
            "date": dt, "field_group": fl,
            "jq_value": jq_v, "local_value": local_v,
            "difference": round(diff, 2), "is_equal": is_eq,
            "comparison_tolerance": tol,
            "evidence_source": "jq: cash_summary/total_summary, local: local_account"
        })

# Per-security position comparison
for dt in pre_div_dates:
    if dt in jq_pos_pivot.index:
        jq_pos_dt = jq_pos_pivot.loc[dt]
        jq_pos_dt = jq_pos_dt[jq_pos_dt > 0]
        local_pos_dt = local_positions.get(dt, {})
        all_secs = set(jq_pos_dt.index) | set(local_pos_dt.keys())
        for sec in sorted(all_secs):
            jq_qty = int(jq_pos_dt[sec]) if sec in jq_pos_dt.index else 0
            local_qty = local_pos_dt.get(sec, 0)
            pre_div_rows.append({
                "date": dt,
                "field_group": f"持仓_{sec}",
                "jq_value": jq_qty,
                "local_value": int(local_qty),
                "difference": jq_qty - int(local_qty),
                "is_equal": jq_qty == int(local_qty),
                "comparison_tolerance": 0,
                "evidence_source": "jq: position_quantity, local: order_exec_tracker"
            })

pre_div_df = pd.DataFrame(pre_div_rows)
pre_div_df.to_csv(OUTPUT_DIR / "pre_divergence_validation.csv", index=False)
print(f"  {len(pre_div_df)} rows")

mismatches = pre_div_df[~pre_div_df["is_equal"]]
acct_mismatches = mismatches[~mismatches["field_group"].str.startswith("持仓_")]
pos_mismatches = mismatches[mismatches["field_group"].str.startswith("持仓_")]
print(f"  Account-level mismatches: {len(acct_mismatches)}")
print(f"  Position-level mismatches: {len(pos_mismatches)}")
if len(acct_mismatches) > 0:
    print("  First account-level mismatches:")
    for _, row in acct_mismatches.head(10).iterrows():
        print(f"    {row['date']} {row['field_group']}: JQ={row['jq_value']} Local={row['local_value']} diff={row['difference']}")

# ============================================================
# 6. DAILY ALIGNMENT
# ============================================================
print("\n[6] Building daily alignment...")

daily_rows = []
first_div_date = None
first_div_field = None

for dt in dates_all:
    jq_c = safe_float(jq_account.loc[dt, "jq_cash"]) if dt in jq_account.index else None
    jq_a = safe_float(jq_account.loc[dt, "jq_total_asset"]) if dt in jq_account.index else None
    jq_pv = safe_float(jq_account.loc[dt, "jq_positions_value"]) if dt in jq_account.index else None
    jq_pc = safe_int(jq_account.loc[dt, "jq_position_count"]) if dt in jq_account.index else 0
    jq_tc = safe_int(jq_account.loc[dt, "jq_trade_count"]) if dt in jq_account.index else 0
    
    lc = safe_float(local_account.loc[dt, "local_cash"]) if dt in local_account.index else None
    la = safe_float(local_account.loc[dt, "local_total_asset"]) if dt in local_account.index else None
    lpv = safe_float(local_account.loc[dt, "local_positions_value"]) if dt in local_account.index else None
    lpc = safe_int(local_account.loc[dt, "local_position_count"]) if dt in local_account.index else 0
    ltc = safe_int(local_account.loc[dt, "local_trade_count"]) if dt in local_account.index else 0
    
    cash_diff = round(lc - jq_c, 2) if jq_c is not None and lc is not None else None
    asset_diff = round(la - jq_a, 2) if jq_a is not None and la is not None else None
    pv_diff = round(lpv - jq_pv, 2) if jq_pv is not None and lpv is not None else None
    pc_diff = lpc - jq_pc if jq_pc is not None else None
    tc_diff = ltc - jq_tc if jq_tc is not None else None
    
    # Find first difference
    first_diff = None
    fdf = ""
    if abs(cash_diff or 0) > 0.01:
        first_diff = "cash"
    elif abs(asset_diff or 0) > 0.01:
        first_diff = "total_asset"
    elif abs(pv_diff or 0) > 0.01:
        first_diff = "positions_value"
    elif pc_diff != 0:
        first_diff = "position_count"
    elif tc_diff != 0:
        first_diff = "trade_count"
    
    if first_diff and first_div_date is None:
        first_div_date = dt
        first_div_field = first_diff
        fdf = first_diff
    
    if first_div_date is None:
        status = "MATCH"
    elif dt == first_div_date:
        status = "ROOT_DIVERGENCE"
    else:
        status = "CASCADE_DIVERGENCE"
    
    daily_rows.append({
        "date": dt,
        "jq_start_cash": jq_c,
        "local_start_cash": lc,
        "jq_start_asset": jq_a,
        "local_start_asset": la,
        "jq_end_cash": jq_c, "local_end_cash": lc,
        "jq_end_asset": jq_a, "local_end_asset": la,
        "jq_trade_count": jq_tc, "local_order_count": ltc, "local_fill_count": ltc,
        "jq_position_count": jq_pc, "local_position_count": lpc,
        "cash_difference": cash_diff, "asset_difference": asset_diff,
        "first_difference_field": fdf,
        "alignment_status": status,
    })

daily_df = pd.DataFrame(daily_rows)
daily_df.to_csv(OUTPUT_DIR / "daily_alignment.csv", index=False)
print(f"  {len(daily_df)} rows")
print(f"  First divergence: {first_div_date}, field={first_div_field}")
mc = len(daily_df[daily_df["alignment_status"] == "MATCH"])
rc = len(daily_df[daily_df["alignment_status"] == "ROOT_DIVERGENCE"])
cc = len(daily_df[daily_df["alignment_status"] == "CASCADE_DIVERGENCE"])
print(f"  MATCH={mc}, ROOT={rc}, CASCADE={cc}")

# Show alignment for key dates around first divergence
if first_div_date:
    idx = dates_all.index(first_div_date)
    for i in range(max(0, idx-1), min(len(dates_all), idx+3)):
        r = daily_df.iloc[i]
        print(f"    {r['date']}: cash_diff={r['cash_difference']}, asset_diff={r['asset_difference']}, pos_diff={r['jq_position_count']-r['local_position_count']}, status={r['alignment_status']}")

# ============================================================
# 7. TRADE ALIGNMENT
# ============================================================
print("\n[7] Building trade alignment...")

jq_trades_by_date = {}
for dt, grp in jq_trades.groupby("trade_date"):
    jq_trades_by_date[dt] = grp.reset_index(drop=True)
local_trades_by_date = {}
for dt, grp in local_trades.groupby("trade_date"):
    local_trades_by_date[dt] = grp.reset_index(drop=True)

trade_rows = []
for dt in dates_all:
    jq_t = jq_trades_by_date.get(dt, pd.DataFrame())
    local_t = local_trades_by_date.get(dt, pd.DataFrame())
    rejs = rejection_logs.get(dt, [])
    
    for i, jr in jq_t.iterrows():
        sec = jr["normalized_security_code"]
        jq_side = jr["side"]
        jq_qty = int(jr["quantity"])
        jq_price = float(jr["price"])
        
        local_match = pd.DataFrame()
        if not local_t.empty and "code" in local_t.columns:
            local_match = local_t[local_t["code"] == sec]
        
        local_qty = 0
        local_price = None
        local_status = "NOT_FOUND"
        rej_reason = ""
        
        if len(local_match) > 0:
            lr = local_match.iloc[0]
            local_qty = int(lr["abs_amount"])
            local_price = float(lr["price"])
            if jq_qty == local_qty and abs(jq_price - local_price) < 0.01 and jq_side == lr["side"]:
                local_status = "FILLED_MATCH"
            elif jq_qty == local_qty and abs(jq_price - local_price) < 0.01:
                local_status = "FILLED_SIDE_MISMATCH"
            else:
                local_status = "FILLED_QUANTITY_PRICE_MISMATCH"
        else:
            for rej in rejs:
                if rej["security"] == sec:
                    rej_reason = rej["reason"]
                    local_status = "REJECTED"
                    break
        
        if local_status == "FILLED_MATCH":
            al = "MATCH"
        elif local_status.startswith("FILLED"):
            al = "MISMATCH"
        elif local_status == "REJECTED":
            al = "DIVERGENCE"
        else:
            al = "MISSING"
        
        trade_rows.append({
            "date": dt, "sequence": i, "security": sec, "side": jq_side,
            "jq_quantity": jq_qty,
            "local_requested_quantity": local_qty if local_status != "NOT_FOUND" else 0,
            "local_filled_quantity": local_qty if local_status != "NOT_FOUND" else 0,
            "jq_price": jq_price, "local_price": local_price,
            "local_order_status": local_status,
            "local_rejection_reason": rej_reason,
            "alignment_status": al,
        })

trade_df = pd.DataFrame(trade_rows)
trade_df.to_csv(OUTPUT_DIR / "trade_alignment.csv", index=False)
print(f"  {len(trade_df)} rows")
if len(trade_df) > 0:
    for al, cnt in trade_df["alignment_status"].value_counts().items():
        print(f"    {al}: {cnt}")

# ============================================================
# 8. POSITION ALIGNMENT
# ============================================================
print("\n[8] Building position alignment...")

pos_rows = []
for dt in dates_all:
    jq_pos_dt = {}
    if dt in jq_pos_pivot.index:
        row = jq_pos_pivot.loc[dt]
        for sec in row.index:
            qty = row[sec]
            if qty > 0:
                jq_pos_dt[sec] = int(round(qty))
    local_pos_dt = local_positions.get(dt, {})
    all_secs = set(jq_pos_dt.keys()) | set(local_pos_dt.keys())
    for sec in sorted(all_secs):
        jq_qty = jq_pos_dt.get(sec, 0)
        local_qty = int(local_pos_dt.get(sec, 0))
        diff = jq_qty - local_qty
        if diff == 0:
            al = "MATCH"
        elif sec not in local_pos_dt:
            al = "JQ_ONLY"
        elif sec not in jq_pos_dt:
            al = "LOCAL_ONLY"
        else:
            al = "QUANTITY_DIFF"
        pos_rows.append({
            "date": dt, "snapshot_type": "END_OF_DAY",
            "security": sec,
            "jq_quantity": jq_qty, "local_quantity": local_qty,
            "quantity_difference": diff,
            "alignment_status": al,
        })

pos_df = pd.DataFrame(pos_rows)
pos_df.to_csv(OUTPUT_DIR / "position_alignment.csv", index=False)
print(f"  {len(pos_df)} rows")

# ============================================================
# 9. ORDER-FILL ALIGNMENT
# ============================================================
print("\n[9] Building order-fill alignment...")

of_rows = []
for dt in dates_all:
    jq_t = jq_trades_by_date.get(dt, pd.DataFrame())
    local_t = local_trades_by_date.get(dt, pd.DataFrame())
    rejs = rejection_logs.get(dt, [])
    
    for _, jr in jq_t.iterrows():
        sec = jr["normalized_security_code"]
        jq_qty = int(jr["quantity"])
        jq_price = float(jr["price"])
        
        local_match = pd.DataFrame()
        if not local_t.empty and "code" in local_t.columns:
            local_match = local_t[local_t["code"] == sec]
        local_fill_qty = int(local_match["abs_amount"].sum()) if len(local_match) > 0 else 0
        local_fill_price = float(local_match["price"].iloc[0]) if len(local_match) > 0 else None
        
        rej_reason = ""
        for rej in rejs:
            if rej["security"] == sec:
                rej_reason = rej["reason"]
                break
        
        of_rows.append({
            "date": dt, "security": sec, "side": jr["side"],
            "jq_quantity": jq_qty, "jq_price": jq_price,
            "local_filled_quantity": local_fill_qty,
            "local_filled_price": local_fill_price,
            "order_intent_buy_target": None,
            "order_intent_sell_target": None,
            "rejection_reason": rej_reason,
            "alignment": "MATCH" if local_fill_qty == jq_qty else f"LOCAL={local_fill_qty}",
        })

of_df = pd.DataFrame(of_rows)
of_df.to_csv(OUTPUT_DIR / "order_fill_alignment.csv", index=False)
print(f"  {len(of_df)} rows")

# ============================================================
# 10. FIRST DIVERGENCE - DETAILED ANALYSIS
# ============================================================
print(f"\n[10] First divergence analysis: {first_div_date}")

first_div = {
    "first_divergence_date": first_div_date,
    "first_divergence_time": None,
    "security": None,
    "field": first_div_field,
    "jq_value": None,
    "local_value": None,
    "jq_previous_state": None,
    "local_previous_state": None,
    "jq_current_event": None,
    "local_current_event": None,
    "local_order_intent": None,
    "local_order_result": None,
    "local_rejection_reason": None,
    "root_or_cascade": "ROOT",
    "evidence_level": "PARTIAL",
    "candidate_root_cause": "PENDING_ANALYSIS",
    "unresolved_questions": []
}

if first_div_date:
    dr = daily_df[daily_df["date"] == first_div_date].iloc[0]
    first_div["jq_value"] = float(dr["jq_end_" + first_div_field.replace("cash","cash").replace("total_asset","asset").replace("positions_value","positions_value")]) if hasattr(dr, f"jq_end_{first_div_field}") else float(dr["jq_end_cash"])
    first_div["local_value"] = float(dr["local_end_cash"])
    
    # Check for trade-level divergence on this date
    div_trades = trade_df[(trade_df["date"] == first_div_date) & (trade_df["alignment_status"] != "MATCH")]
    if len(div_trades) > 0:
        dt_row = div_trades.iloc[0]
        first_div["security"] = dt_row["security"]
        first_div["first_divergence_time"] = "09:30:00"
        first_div["jq_current_event"] = f"JQ trade: {dt_row['side']} {int(dt_row['jq_quantity'])}@{dt_row['jq_price']} of {dt_row['security']}"
        first_div["local_order_intent"] = int(dt_row["local_requested_quantity"]) if not pd.isna(dt_row.get("local_requested_quantity", 0)) else 0
        first_div["local_order_result"] = dt_row["local_order_status"]
        first_div["local_rejection_reason"] = dt_row["local_rejection_reason"]
        first_div["candidate_root_cause"] = "LOCAL_LIMIT_DOWN_REJECTION" if dt_row["local_rejection_reason"] else "TRADE_EXECUTION_MISMATCH"
    
    # Previous day state
    prev_idx = dates_all.index(first_div_date) - 1
    if prev_idx >= 0:
        prev_dt = dates_all[prev_idx]
        if prev_dt in jq_account.index:
            first_div["jq_previous_state"] = {
                "date": prev_dt,
                "cash": float(jq_account.loc[prev_dt, "jq_cash"]),
                "total_asset": float(jq_account.loc[prev_dt, "jq_total_asset"]),
                "positions_value": float(jq_account.loc[prev_dt, "jq_positions_value"]),
            }
        if prev_dt in local_account.index:
            first_div["local_previous_state"] = {
                "date": prev_dt,
                "cash": float(local_account.loc[prev_dt, "local_cash"]),
                "total_asset": float(local_account.loc[prev_dt, "local_total_asset"]),
                "positions_value": float(local_account.loc[prev_dt, "local_positions_value"]),
            }
    
    # Evidence level
    if first_div["jq_previous_state"] and first_div["local_previous_state"]:
        jpc = first_div["jq_previous_state"]["cash"]
        lpc = first_div["local_previous_state"]["cash"]
        jpa = first_div["jq_previous_state"]["total_asset"]
        lpa = first_div["local_previous_state"]["total_asset"]
        if abs(jpc - lpc) < 0.01 and abs(jpa - lpa) < 0.01:
            first_div["evidence_level"] = "STRONG"
            first_div["candidate_root_cause"] = first_div.get("candidate_root_cause", "CASH_TOTAL_MISMATCH")

with open(OUTPUT_DIR / "first_divergence.json", "w", encoding="utf-8") as f:
    json.dump(first_div, f, indent=2, ensure_ascii=False, default=str)
print(f"  Evidence level: {first_div['evidence_level']}")
print(f"  Candidate root cause: {first_div['candidate_root_cause']}")

# ============================================================
# 11. LIMIT STATE FORENSICS
# ============================================================
print("\n[11] Building limit state forensics...")

import pyarrow.parquet as pq
HDATA_ROOT = r"D:\Work Space\HData"

def normalize_to_hdata_code(sec):
    """Convert 301098.XSHE -> 301098.SZ, 600000.XSHG -> 600000.SH"""
    if sec.endswith(".XSHE"):
        return sec.replace(".XSHE", ".SZ")
    if sec.endswith(".XSHG"):
        return sec.replace(".XSHG", ".SH")
    return sec

def get_hdata_1d(security, date_str):
    try:
        year = date_str[:4]
        fp = os.path.join(HDATA_ROOT, "data", "processed", "1d_stock", f"{year}.parquet")
        if not os.path.exists(fp):
            return None
        hdata_code = normalize_to_hdata_code(security)
        table = pq.read_table(fp, columns=["code", "date", "open", "high", "low", "close", "pre_close", "pct_chg"])
        df = table.to_pandas()
        df["code"] = df["code"].astype(str)
        df["date"] = df["date"].astype(str)
        hdata_date = date_str.replace("-", "")
        row = df[(df["code"] == hdata_code) & (df["date"] == hdata_date)]
        if len(row) == 0:
            return {"not_found": True, "hdata_code": hdata_code}
        return row.iloc[0].to_dict()
    except Exception as e:
        return {"error": str(e)}

def calc_limits(prev_close, security):
    try:
        prev_close = float(prev_close)
        if security.endswith(".SH"):
            tick = 0.001 if prev_close < 1 else 0.01
            hl = round(prev_close * 1.10 / tick) * tick
            ll = round(prev_close * 0.90 / tick) * tick
        elif security.endswith(".BJ"):
            hl = round(prev_close * 1.30 / 0.01) * 0.01
            ll = round(prev_close * 0.70 / 0.01) * 0.01
        else:
            code_num = int(security.split(".")[0])
            if 300000 <= code_num < 400000:
                hl = round(prev_close * 1.20 / 0.01) * 0.01
                ll = round(prev_close * 0.80 / 0.01) * 0.01
            else:
                hl = round(prev_close * 1.10 / 0.01) * 0.01
                ll = round(prev_close * 0.90 / 0.01) * 0.01
        return hl, ll
    except:
        return None, None

limit_rows = []
for dt, rejs in sorted(rejection_logs.items()):
    for rej in rejs:
        sec = rej["security"]
        hdata = get_hdata_1d(sec, dt)
        jq_match = jq_trades[(jq_trades["trade_date"] == dt) & (jq_trades["normalized_security_code"] == sec)]
        jq_trade_qty = int(jq_match["quantity"].sum()) if len(jq_match) > 0 else 0
        jq_trade_price = float(jq_match["price"].iloc[0]) if len(jq_match) > 0 else None
        prev_close = hdata.get("pre_close") if hdata else None
        hl, ll = calc_limits(prev_close, sec) if prev_close else (None, None)
        limit_rows.append({
            "date": dt, "event_time": rej["time"], "security": sec,
            "previous_close": prev_close,
            "open": hdata.get("open") if hdata else None,
            "high": hdata.get("high") if hdata else None,
            "low": hdata.get("low") if hdata else None,
            "close": hdata.get("close") if hdata else None,
            "high_limit": hl, "low_limit": ll,
            "engine_rejection_reason": rej["reason"],
            "jq_trade_quantity": jq_trade_qty,
            "jq_trade_price": jq_trade_price,
            "jq_trade_time": "09:30:00" if jq_trade_qty > 0 else None,
        })

limit_df = pd.DataFrame(limit_rows)
limit_df.to_csv(OUTPUT_DIR / "limit_state_forensics.csv", index=False)
print(f"  {len(limit_df)} rows")

if len(limit_df) > 0:
    print("  Sample: first div date rows:")
    if first_div_date:
        div_limit = limit_df[limit_df["date"] == first_div_date]
        if len(div_limit) > 0:
            print(div_limit.to_string())

# ============================================================
# 12. REJECTION CLASSIFICATION
# ============================================================
print("\n[12] Rejection classification...")

rej_rows = []
fd = first_div_date
first_div_sec = first_div.get("security") if first_div else None

for dt, rejs in sorted(rejection_logs.items()):
    for i, rej in enumerate(rejs):
        sec = rej["security"]
        if fd and dt < fd:
            relation = "BEFORE_FIRST_DIVERGENCE"
        elif fd and dt == fd:
            if sec == first_div_sec:
                relation = "FIRST_DIVERGENCE"
            else:
                relation = "POSSIBLE_INDEPENDENT_DIVERGENCE"
        elif fd and dt > fd:
            relation = "CASCADE_AFTER_FIRST_DIVERGENCE"
        else:
            relation = "UNRESOLVED"
        rej_rows.append({
            "date": dt, "event_time": rej["time"], "security": sec,
            "rejection_reason": rej["reason"],
            "relation_to_first_divergence": relation,
            "dividend_note": "",
        })

rej_df = pd.DataFrame(rej_rows)
rej_df.to_csv(OUTPUT_DIR / "rejection_classification.csv", index=False)
print(f"  {len(rej_df)} rows")
if len(rej_df) > 0:
    for cat, cnt in rej_df["relation_to_first_divergence"].value_counts().items():
        print(f"    {cat}: {cnt}")

# ============================================================
# 13. SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("TASK-MICROCAP-003C SUMMARY")
print("=" * 60)

print(f"\n  First divergence date: {first_div_date}")
print(f"  First divergence field: {first_div_field}")
if first_div:
    print(f"  First divergence security: {first_div['security']}")
    print(f"  Evidence level: {first_div['evidence_level']}")
    print(f"  Candidate root cause: {first_div['candidate_root_cause']}")

print(f"\n  Account-level MATCH days before divergence: {len([d for d in daily_rows if d['alignment_status']=='MATCH'])}")
print(f"  The last completely consistent date before divergence:")
if first_div_date:
    fidx = dates_all.index(first_div_date)
    if fidx > 0:
        print(f"    {dates_all[fidx-1]}")
        
print(f"\n  Trade alignment summary:")
if len(trade_df) > 0:
    for al, cnt in trade_df["alignment_status"].value_counts().items():
        print(f"    {al}: {cnt}")

print(f"\n  Files generated:")
for fn in [
    "pre_divergence_validation.csv", "daily_alignment.csv",
    "trade_alignment.csv", "position_alignment.csv",
    "order_fill_alignment.csv", "limit_state_forensics.csv",
    "rejection_classification.csv", "first_divergence.json",
]:
    fp = OUTPUT_DIR / fn
    if fp.exists():
        print(f"    {fn}: {fp.stat().st_size} bytes")
    else:
        print(f"    {fn}: MISSING")

print(f"\n  Next steps:")
print(f"    1. Review daily_alignment.csv for first divergence date/field")
print(f"    2. Review trade_alignment.csv for trade-level divergence on that date")
print(f"    3. Review limit_state_forensics.csv for limit price vs JQ trade price")
print(f"    4. Write first_divergence.md with full forensic analysis")
print(f"    5. Write task_003c_report.md with final conclusions")
