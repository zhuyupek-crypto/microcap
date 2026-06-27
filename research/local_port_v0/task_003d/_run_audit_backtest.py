#!/usr/bin/env python3
"""Run audit strategy through local_quant engine, collect structured logs."""
import os, sys, json, hashlib
from pathlib import Path

LQ_ROOT = r"D:\Work Space\local_quant"
sys.path.insert(0, LQ_ROOT)
os.environ.setdefault("HDATA_ROOT", r"D:\Work Space\HData")
os.environ.setdefault("LOCAL_QUANT_HDATA_SOURCE", "legacy")

STRATEGY_PATH = r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003d\微盘股-母版-20260627-audit.py"
OUTPUT_DIR = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003d")
LOG_PATH = OUTPUT_DIR / "local_audit_20260514.jsonl"
EXPECTED_SHA = "F363464FA55218C5B721D9286449C99A0C9ACC097524B6F5F3DB89A13AF151D6"

print("=" * 60)
print("TASK-003D1: Audit backtest run")
print("=" * 60)

# Verify original strategy SHA unchanged
orig_path = r"D:\Work Space\他山之石\微盘股\微盘股-母版-20260627.py"
with open(orig_path, "rb") as f:
    orig_sha = hashlib.sha256(f.read()).hexdigest().upper()
if orig_sha == EXPECTED_SHA:
    print(f"[OK] Original strategy SHA: {orig_sha[:16]}...")
else:
    print(f"[ERR] Original strategy SHA mismatch! Expected {EXPECTED_SHA[:16]}..., got {orig_sha[:16]}...")
    sys.exit(1)

# Set up audit environment
os.environ["AUDIT_RUN_ID"] = "audit_local_003d1"
os.environ["AUDIT_LOG_PATH"] = str(LOG_PATH)

# Clear existing audit log
if LOG_PATH.exists():
    LOG_PATH.unlink()

# Import engine
import pandas as pd
from engine.core import Engine
import importlib
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

# Read audit strategy
with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
    strategy_code = f.read()

# Run
start_date = "2026-05-01"
end_date = "2026-05-15"
initial_cash = 1_000_000

print(f"\nRunning audit backtest {start_date} -> {end_date}, cash={initial_cash}")
print(f"Audit log: {LOG_PATH}")

engine = Engine(
    strategy_code=strategy_code,
    start_date=start_date,
    end_date=end_date,
    initial_cash=initial_cash,
    frequency="daily",
)

# Run
equity, trades, logs, metrics = engine.run()

print(f"\nBacktest complete:")
print(f"  Trading days: {len(equity)}")
print(f"  Trades: {len(trades)}")
print(f"  Final value: {metrics.get('total_return', 'N/A')}")

# Save engine trades
if trades is not None and not trades.empty:
    trades.to_csv(OUTPUT_DIR / "audit_local_trades.csv", index=False)
    print(f"  Trades saved: {len(trades)}")

# Save engine logs
with open(OUTPUT_DIR / "audit_local_engine_logs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(logs))
print(f"  Log lines: {len(logs)}")

# Count audit log entries
if LOG_PATH.exists():
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        audit_entries = [line for line in f if line.strip()]
    print(f"  Audit log entries: {len(audit_entries)}")
else:
    print("  WARNING: Audit log file not found!")
    audit_entries = []

# Show summary of 2026-05-14 audit entries
print("\n=== 300405.XSHE audit entries on 2026-05-14 ===")
for line in audit_entries:
    entry = json.loads(line)
    sec = entry.get("security", "")
    ed = str(entry.get("event_date", "") or entry.get("current_dt", "") or "")
    if ("300405" in str(sec) or ("300405" in str(entry.get("target_list", "")))) and "2026-05-14" in str(entry):
        print(f"  [{entry.get('event_type')}] {json.dumps({k:v for k,v in entry.items() if k not in ('run_id','strategy_sha256','event_sequence')}, ensure_ascii=False)}")

# Quick reproduction check
print("\n=== Reproduction check (pre-divergence matches) ===")
jq_trades = pd.read_csv(OUTPUT_DIR.parent / "task_003" / "jq_trades_normalized.csv")
jq_trades["trade_date"] = jq_trades["trade_date"].astype(str)

audit_local_trades = trades
if audit_local_trades is not None and not audit_local_trades.empty:
    for dt in ["2026-05-06", "2026-05-07", "2026-05-08", "2026-05-11", "2026-05-12", "2026-05-13"]:
        jq_day = jq_trades[jq_trades["trade_date"] == dt]
        # We can't directly compare trades because the engine output format differs
        print(f"  {dt}: JQ trades={len(jq_day)}, Local trades={len(audit_local_trades[audit_local_trades['time'].astype(str).str[:10] == dt])}")

print("\nDone. See local_audit_20260514.jsonl for full structured audit log.")
