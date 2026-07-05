#!/usr/bin/env python3
"""TASK-006E Stage E2: Signal Replay Module (degraded mode).

Replays historical backtest outputs (trades.csv + engine_logs.txt) and converts
them into pilot daily_signal format.

This is the DEGRADED MODE implementation (path D):
- Uses HData historical backtest outputs (r3_full_2020_202605_research)
- Does NOT require live data source
- Validates engineering pipeline only, NOT live executability

Inputs:
  - trades.csv (filled orders)
  - engine_logs.txt (rejected orders, phase targets, defense plans)
  - manifest.json (rejection reasons summary)

Outputs:
  - daily_signal_YYYYMMDD.csv (per-day signal list)
  - daily_signal_summary.csv (cross-day summary)
  - SIGNAL_REPLAY_REPORT.md (validation report)
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
RUN_DIR = PROJECT_ROOT / "research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research"
TRADES_CSV = RUN_DIR / "trades.csv"
ENGINE_LOGS = RUN_DIR / "engine_logs.txt"
MANIFEST_JSON = RUN_DIR / "manifest.json"

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_trades(path: Path) -> list[dict[str, Any]]:
    """Load trades.csv, return list of trade dicts."""
    trades = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            time_str = row["time"]
            amount = int(row["amount"])
            trades.append({
                "date": time_str[:10],
                "time": time_str,
                "code": row["code"],
                "side": "buy" if amount > 0 else "sell",
                "quantity": abs(amount),
                "price": float(row["price"]),
                "commission": float(row["commission"]) if row["commission"] else 0.0,
                "tax": float(row["tax"]) if row["tax"] else 0.0,
                "trade_id": row["trade_id"],
                "order_id": row["order_id"],
            })
    return trades


def parse_engine_logs(path: Path) -> dict[str, dict[str, Any]]:
    """Parse engine_logs.txt to extract per-day signal context.

    Extracts:
    - rejected orders (with reason)
    - phase offset targets (selection results)
    - defense plan
    - days counter / defensive flag
    """
    days: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "rejected_orders": [],
        "phase_targets": {},
        "defense_plan": "",
        "defensive": False,
        "trade_enabled": True,
        "due_offsets": [],
    })

    log_re = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] INFO: (.+)$")
    reject_re = re.compile(r"Rejected (?:market (?:buy|sell)|sell order) for (\d{6}\.\w+?)[\s:]+(.+?)(?:$)")
    phase_re = re.compile(r"phase offset=(\d+) targets=(.*)$")
    defense_re = re.compile(r"sell_defense_plan: (.+)$")
    days_re = re.compile(r"days=(\d+) defensive=(True|False) trade_enabled=(True|False) due_offsets=\[([^\]]*)\]")

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = log_re.match(line.strip())
            if not m:
                continue
            date, _time, msg = m.groups()

            rj = reject_re.match(msg)
            if rj:
                code, reason = rj.groups()
                days[date]["rejected_orders"].append({"code": code, "reason": reason})
                continue

            ph = phase_re.match(msg)
            if ph:
                offset, targets = ph.groups()
                days[date]["phase_targets"][offset] = targets
                continue

            df = defense_re.match(msg)
            if df:
                days[date]["defense_plan"] = df.group(1)
                continue

            dy = days_re.match(msg)
            if dy:
                d_counter, defensive, trade_enabled, due_offsets = dy.groups()
                days[date]["defensive"] = (defensive == "True")
                days[date]["trade_enabled"] = (trade_enabled == "True")
                days[date]["due_offsets"] = [x for x in due_offsets.split(",") if x]
                continue

    return dict(days)


def classify_signal(trade: dict, day_ctx: dict) -> str:
    """Classify a trade into a signal reason.

    Mapping:
    - buy + defensive day + 511880.XSHG → buy_defense (defensive cash parking)
    - buy + new code (not in prior positions) → buy_new
    - buy + existing code → buy_add
    - sell + defense_plan contains code → sell_defense
    - sell + limit up context → sell_limit_up_14h (heuristic, may need refinement)
    - sell + other → sell_phase
    """
    code = trade["code"]
    side = trade["side"]

    if side == "buy":
        if day_ctx.get("defensive") and code == "511880.XSHG":
            return "buy_defense"
        return "buy_new"  # simplified; full buy_add detection needs position tracking

    if side == "sell":
        defense_plan = day_ctx.get("defense_plan", "")
        if defense_plan and code in defense_plan:
            return "sell_defense"
        return "sell_phase"

    return "unknown"


def build_daily_signals(
    trades: list[dict],
    log_ctx: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Build per-day signal lists.

    Returns: {date: [signal_row, ...]}
    """
    daily: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for t in trades:
        date = t["date"]
        ctx = log_ctx.get(date, {})
        reason = classify_signal(t, ctx)

        daily[date].append({
            "date": date,
            "code": t["code"],
            "action": t["side"],
            "target_value": round(t["quantity"] * t["price"], 2),
            "target_qty": t["quantity"],
            "price": t["price"],
            "reason": reason,
            "phase_index": "",
            "defense_flag": ctx.get("defensive", False),
            "trade_id": t["trade_id"],
        })

    # Add rejected orders as skip signals
    for date, ctx in log_ctx.items():
        for rj in ctx.get("rejected_orders", []):
            daily[date].append({
                "date": date,
                "code": rj["code"],
                "action": "skip",
                "target_value": 0,
                "target_qty": 0,
                "price": 0,
                "reason": "skip_cash_insufficient",
                "phase_index": "",
                "defense_flag": ctx.get("defensive", False),
                "trade_id": "",
                "rejection_reason": rj["reason"],
            })

    return dict(daily)


def write_daily_csv(daily: dict[str, list[dict]], out_dir: Path) -> int:
    """Write per-day signal CSV files. Returns count of files written."""
    count = 0
    for date in sorted(daily.keys()):
        rows = daily[date]
        out_path = out_dir / f"daily_signal_{date.replace('-', '')}.csv"
        fields = [
            "date", "code", "action", "target_value", "target_qty", "price",
            "reason", "phase_index", "defense_flag", "trade_id", "rejection_reason",
        ]
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        count += 1
    return count


def write_summary_csv(daily: dict[str, list[dict]], out_path: Path) -> None:
    """Write cross-day summary CSV."""
    rows = []
    for date in sorted(daily.keys()):
        signals = daily[date]
        action_counter = Counter(s["action"] for s in signals)
        reason_counter = Counter(s["reason"] for s in signals)
        rows.append({
            "date": date,
            "total_signals": len(signals),
            "buy_count": action_counter.get("buy", 0),
            "sell_count": action_counter.get("sell", 0),
            "skip_count": action_counter.get("skip", 0),
            "buy_new": reason_counter.get("buy_new", 0),
            "buy_defense": reason_counter.get("buy_defense", 0),
            "sell_phase": reason_counter.get("sell_phase", 0),
            "sell_defense": reason_counter.get("sell_defense", 0),
            "skip_cash_insufficient": reason_counter.get("skip_cash_insufficient", 0),
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for r in rows:
                writer.writerow(r)


def validate_against_manifest(daily: dict[str, list[dict]], manifest: dict) -> dict[str, Any]:
    """Cross-validate signal counts against manifest.json."""
    total_fills = sum(
        1 for signals in daily.values()
        for s in signals if s["action"] in ("buy", "sell")
    )
    total_rejected = sum(
        1 for signals in daily.values()
        for s in signals if s["action"] == "skip"
    )

    manifest_fills = manifest.get("orders_filled", 0)
    manifest_rejected = manifest.get("orders_rejected", 0)

    return {
        "signal_fills_count": total_fills,
        "manifest_fills_count": manifest_fills,
        "fills_match": total_fills == manifest_fills,
        "signal_rejected_count": total_rejected,
        "manifest_rejected_count": manifest_rejected,
        "rejected_match": total_rejected == manifest_rejected,
    }


def main() -> None:
    print("=" * 70)
    print("TASK-006E Stage E2: Signal Replay (degraded mode)")
    print("=" * 70)

    print("\n[1] Loading backtest outputs...")
    trades = load_trades(TRADES_CSV)
    print(f"  Trades loaded: {len(trades)}")
    log_ctx = parse_engine_logs(ENGINE_LOGS)
    print(f"  Log context days: {len(log_ctx)}")
    with open(MANIFEST_JSON, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    print(f"  Manifest loaded: {manifest.get('tag')}")

    print("\n[2] Building daily signals...")
    daily = build_daily_signals(trades, log_ctx)
    total_days = len(daily)
    total_signals = sum(len(v) for v in daily.values())
    print(f"  Trading days with signals: {total_days}")
    print(f"  Total signal rows: {total_signals}")

    print("\n[3] Writing per-day CSV files...")
    files_written = write_daily_csv(daily, OUTPUT_DIR)
    print(f"  Files written: {files_written}")
    print(f"  Output dir: {OUTPUT_DIR}")

    print("\n[4] Writing summary CSV...")
    summary_path = OUTPUT_DIR / "daily_signal_summary.csv"
    write_summary_csv(daily, summary_path)
    print(f"  -> {summary_path}")

    print("\n[5] Validating against manifest...")
    validation = validate_against_manifest(daily, manifest)
    for k, v in validation.items():
        print(f"  {k}: {v}")

    print("\n[6] Signal reason distribution:")
    reason_counter = Counter()
    for signals in daily.values():
        for s in signals:
            reason_counter[s["reason"]] += 1
    for reason, count in reason_counter.most_common():
        print(f"  {reason}: {count}")

    print("\n[E2] Done.")


if __name__ == "__main__":
    main()
