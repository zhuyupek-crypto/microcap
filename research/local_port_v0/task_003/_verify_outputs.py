#!/usr/bin/env python3
"""Verify parser outputs."""
import csv
from collections import defaultdict

OUT = r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003"

print("=== Trades ===")
with open(f"{OUT}/jq_trades_normalized.csv", "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
print(f"  Total: {len(rows)}")

# Side distribution
sides = defaultdict(int)
for r in rows:
    sides[r["side"]] += 1
print(f"  Side dist: {dict(sides)}")

# Date distribution
dates = defaultdict(int)
for r in rows:
    dates[r["trade_date"]] += 1
print(f"  Trade dates ({len(dates)}): {sorted(dates.keys())}")

# Sells
sells = [r for r in rows if r["side"] == "sell"]
print(f"  Sells ({len(sells)}):")
for s in sells[:5]:
    print(f"    {s['trade_date']} {s['normalized_security_code']} qty={s['quantity']} @ {s['price']} amt={s['gross_amount']}")

# First/last
print(f"  First: {rows[0]['trade_date']} {rows[0]['normalized_security_code']} {rows[0]['side']}")
print(f"  Last:  {rows[-1]['trade_date']} {rows[-1]['normalized_security_code']} {rows[-1]['side']}")

# Securities
secs = set(r["normalized_security_code"] for r in rows if r["normalized_security_code"])
print(f"  Securities ({len(secs)}): {sorted(secs)}")

# Check duplicate detection
exact_dup = [r for r in rows if r["is_exact_duplicate"] == "True"]
print(f"  Exact duplicates: {len(exact_dup)}")

print()
print("=== Portfolio ===")
with open(f"{OUT}/jq_portfolio_normalized.csv", "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
print(f"  Total: {len(rows)}")

types = defaultdict(int)
for r in rows:
    types[r["snapshot_type"]] += 1
print(f"  Types: {dict(types)}")

# Date range
dates = set(r["record_date"] for r in rows if r["record_date"])
print(f"  Date range: {min(dates)} to {max(dates)} ({len(dates)} dates)")

# Cash and total
cash_rows = [r for r in rows if r["snapshot_type"] == "cash_summary" and r["available_cash"]]
total_rows = [r for r in rows if r["snapshot_type"] == "total_summary" and r["total_asset"]]
if cash_rows:
    print(f"  First cash: {cash_rows[0]['record_date']} = {cash_rows[0]['available_cash']}")
    print(f"  Last cash:  {cash_rows[-1]['record_date']} = {cash_rows[-1]['available_cash']}")
if total_rows:
    print(f"  First total: {total_rows[0]['record_date']} = {total_rows[0]['total_asset']}")
    print(f"  Last total:  {total_rows[-1]['record_date']} = {total_rows[-1]['total_asset']}")

# Sample position row
pos_rows = [r for r in rows if r["snapshot_type"] == "position" and r["normalized_security_code"]]
print(f"  Sample positions:")
for p in pos_rows[:3]:
    print(f"    {p['record_date']} {p['normalized_security_code']} {p['security_name']} qty={p['position_quantity']} mv={p['market_value']}")

print()
print("=== Daily Reconciliation ===")
with open(f"{OUT}/jq_daily_reconciliation.csv", "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
print(f"  Total: {len(rows)} dates")
# Check first and last
if rows:
    print(f"  First: {rows[0]['date']} trades={rows[0]['num_trades']} buy={rows[0]['buy_amount']} sell={rows[0]['sell_amount']} cash={rows[0]['cash']} asset={rows[0]['total_asset']}")
    print(f"  Last:  {rows[-1]['date']} trades={rows[-1]['num_trades']} buy={rows[-1]['buy_amount']} sell={rows[-1]['sell_amount']} cash={rows[-1]['cash']} asset={rows[-1]['total_asset']}")

print()
print("=== Manifest ===")
import json
with open(f"{OUT}/jq_manifest.json", "r", encoding="utf-8") as f:
    m = json.load(f)
print(f"  Task: {m['task_id']}")
print(f"  Strategy SHA: {m['strategy_sha256'][:16]}...")
for inp in m["input_files"]:
    print(f"  Input: {inp['filename']} ({inp['size_bytes']}B, {inp['total_lines']} lines, SHA={inp['sha256'][:16]}...)")

print()
print("=== Parse Errors ===")
with open(f"{OUT}/jq_parse_errors.csv", "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
print(f"  Total: {len(rows)}")
