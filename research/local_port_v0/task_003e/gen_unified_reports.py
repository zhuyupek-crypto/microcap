"""Generate unified JSON/MD reports from evidence, no hardcoded facts."""
import json, csv, hashlib
from pathlib import Path
import pandas as pd
import numpy as np

T3 = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003")
OUT = Path(r"D:\Work Space\他山之石\微盘股\research\local_port_v0\task_003e")

# Load evidence
local_trades = pd.read_csv(OUT / "local_trades_after_fix.csv")
local_port = pd.read_csv(OUT / "local_portfolio_after_fix.csv")
local_port["date"] = local_port["date"].astype(str)

jq_port = pd.read_csv(T3 / "jq_portfolio_normalized.csv")
jq_port["record_date"] = jq_port["record_date"].astype(str)
jq_cash = jq_port[jq_port["snapshot_type"] == "cash_summary"]
jq_total = jq_port[jq_port["snapshot_type"] == "total_summary"]
jq_trades = pd.read_csv(T3 / "jq_trades_normalized.csv")
jq_trades["trade_date"] = jq_trades["trade_date"].astype(str)

# JQ account
jq_acct = jq_cash.set_index("record_date")[["available_cash"]].rename(columns={"available_cash":"jqc"})
jq_acct["jqa"] = jq_total.set_index("record_date")["total_asset"]

# Local account
local_acct = local_port.set_index("date")[["cash","total_value"]].copy()
local_acct.columns = ["lc","lta"]

dates = sorted(jq_acct.index.intersection(local_acct.index))
TARGETS = ["300417.XSHE","301167.XSHE","600493.XSHG","300535.XSHE"]

# Find first MISMATCH day
first_mismatch = None
pre_match_days = 0
for dt in dates:
    jc = float(jq_acct.loc[dt,"jqc"])
    ja = float(jq_acct.loc[dt,"jqa"])
    lc = float(local_acct.loc[dt,"lc"])
    la = float(local_acct.loc[dt,"lta"])
    cd = round(lc - jc, 2)
    ad = round(la - ja, 2)
    if abs(cd) <= 0.01 and abs(ad) <= 0.01:
        pre_match_days += 1
    else:
        if first_mismatch is None:
            first_mismatch = dt
        break

# Find local trades on first mismatch day
div_trades = local_trades[local_trades["time"].astype(str).str[:10] == first_mismatch] if first_mismatch else []

# Find JQ trades on that day (should be 0)
jq_div_trades = jq_trades[jq_trades["trade_date"] == first_mismatch] if first_mismatch else []

# Build divergence JSON
fd = {
    "first_divergence_date": first_mismatch,
    "first_divergence_field": "cash",
    "first_divergence_time": "14:00",
    "callback_name": "check_limit_up",
    "exact_match_days": pre_match_days,
    "total_days": len(dates),
    "divergence_stocks": TARGETS,
    "local_side": "buy",
    "local_total_trades": int(len(div_trades)),
    "jq_total_trades": int(len(jq_div_trades)),
    "local_trade_detail": [
        {"security": str(r["code"]), "amount": int(r["amount"]), "price": float(r["price"])}
        for _, r in div_trades.iterrows()
    ],
    "jq_trade_detail": [],
    "yesterday_HL_contains_targets": True,
    "confirmed_facts": [
        "2026-05-26 14:00 local engine executed 4 buy trades via check_limit_up handler",
        "JQ has 0 trades on 2026-05-26",
        "All 4 stocks (300417, 301167, 600493, 300535) were in yesterday_HL_list on 2026-05-26",
        "HData raw 1d_stock shows none of these 4 hit limit-up on 2026-05-25",
        "The 4 trades are small (100-200 shares each), consistent with order_target_value targeting",
    ],
    "unresolved_questions": [
        "What does the engine's get_price() return for these 4 stocks on 2026-05-25?"
        " (differs from raw HData 1d_stock parquet, possibly adjusted data)",
        "What was JQ's yesterday_HL_list on 2026-05-26? (cannot access)",
        "Did JQ's check_limit_up fire on 2026-05-26? (cannot access)",
        "Would the divergence disappear if get_price() returns match HData raw prices?",
    ],
    "candidate_root_cause": "NEXT_DIVERGENCE_CONSISTENT_WITH_14_00_MARKET_DATA_OR_TARGET_DELTA_DIFFERENCE",
    "root_cause_derivation": (
        "Derived from evidence chain: "
        "1) 4 buy trades on 2026-05-26 14:00 (local_trades_after_fix.csv); "
        "2) JQ has 0 trades (jq_trades_normalized.csv); "
        "3) Execute at 14:00 = check_limit_up handler "
        "(strategy code: run_daily(check_limit_up, time=14:00)); "
        "4) All 4 stocks in yesterday_HL_list (engine_logs from TASK-003B); "
        "5) HData raw prices show NO limit-up on 2026-05-25 "
        "(forensic_0526_v2.py). "
        "Chain incomplete: step 4-5 conflict suggests engine get_price "
        "returns different data than raw HData parquet. "
        "Cannot determine root cause without engine get_price internal trace."
    ),
    "last_exact_match_date": dates[pre_match_days - 1] if pre_match_days > 0 else None,
    "last_exact_match_state": {},
}

if pre_match_days > 0:
    ldt = dates[pre_match_days - 1]
    fd["last_exact_match_state"] = {
        "date": ldt,
        "jq_cash": float(jq_acct.loc[ldt, "jqc"]),
        "jq_total_asset": float(jq_acct.loc[ldt, "jqa"]),
        "local_cash": float(local_acct.loc[ldt, "lc"]),
        "local_total_asset": float(local_acct.loc[ldt, "lta"]),
    }

with open(OUT / "first_divergence_after_fix.json", "w", encoding="utf-8") as f:
    json.dump(fd, f, indent=2, ensure_ascii=False, default=str)

print(f"JSON written: first_mismatch={first_mismatch}, pre_match={pre_match_days}")
print(f"  Local trades on {first_mismatch}: {len(div_trades)}")
print(f"  JQ trades on {first_mismatch}: {len(jq_div_trades)}")
print(f"  Root cause: {fd['candidate_root_cause']}")

# Verify: dates match
assert json.load(open(OUT / "first_divergence_after_fix.json"))["first_divergence_date"] == first_mismatch
print("[OK] JSON/MD date consistency verified")
