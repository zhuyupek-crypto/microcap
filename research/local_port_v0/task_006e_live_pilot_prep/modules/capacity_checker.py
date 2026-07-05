#!/usr/bin/env python3
r"""TASK-006E Stage E3: Capacity Checker Module (degraded mode).

Replays historical call_auction data to compute participation rate for each
candidate order, and flags whether each order would have been executable
under the conservative pilot thresholds.

This is the DEGRADED MODE implementation (path D):
- Uses HData historical call_auction data (2020+)
- Validates capacity checking engineering pipeline only
- Does NOT verify live executability

Inputs:
  - daily_signal_YYYYMMDD.csv (from E2 signal_replay)
  - call_auction parquet files (D:\Work Space\HData\data\processed\1d_feature\call_auction\)

Outputs:
  - daily_execution_feasibility_YYYYMMDD.csv (per-day feasibility report)
  - capacity_summary.csv (cross-day summary)
  - CAPACITY_CHECKER_REPORT.md (validation report)

Conservative thresholds (from 006D live_pilot_plan.md):
  - auction_participation_rate_limit: 5%
  - min_auction_volume_lots: 100 (1 lot = 100 shares)
  - limit up: buy rejected, sell delayed
  - limit down: sell delayed to next day
  - paused: rejected
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SIGNALS_DIR = Path(__file__).resolve().parents[1] / "reports"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "reports"

HDATA_ROOT = Path(r"D:\Work Space\HData\data\processed")
CALL_AUCTION_DIR = HDATA_ROOT / "1d_feature" / "call_auction"

# Conservative thresholds (006D)
AUCTION_PARTICIPATION_RATE_LIMIT = 0.05  # 5%
MIN_AUCTION_VOLUME_LOTS = 100  # 100 lots = 10000 shares
MIN_AUCTION_VOLUME_SHARES = MIN_AUCTION_VOLUME_LOTS * 100


def load_call_auction(year: int) -> pd.DataFrame:
    """Load call_auction parquet for a given year.

    Returns DataFrame with columns: code, date, current (price), volume (shares).
    """
    path = CALL_AUCTION_DIR / f"{year}.parquet"
    if not path.exists():
        print(f"  WARNING: call_auction file not found: {path}")
        return pd.DataFrame()

    df = pd.read_parquet(path)
    # code is already in format like "000001.XSHE" — no conversion needed
    # Normalize date: int YYYYMMDD -> str YYYY-MM-DD
    if "date" in df.columns:
        d = df["date"].astype(str)
        df["date_str"] = d.str[:4] + "-" + d.str[4:6] + "-" + d.str[6:8]
    return df[["code", "date_str", "current", "volume"]]


def build_auction_lookup(year: int) -> dict[tuple[str, str], dict[str, float]]:
    """Build (code, date) -> {price, volume} lookup for one year.

    Returns: {(code, date_str): {"price": float, "volume": float}}

    Uses vectorized operations instead of iterrows for performance
    (yearly parquet has ~1M+ rows).
    """
    df = load_call_auction(year)
    if df.empty:
        return {}

    # Vectorized: fill NaN, convert to lists, build dict in one pass
    df = df.dropna(subset=["current", "volume"])
    df["current"] = df["current"].astype(float).fillna(0.0)
    df["volume"] = df["volume"].astype(float).fillna(0.0)

    # Build lookup using zip (much faster than iterrows)
    lookup: dict[tuple[str, str], dict[str, float]] = {}
    codes = df["code"].tolist()
    dates = df["date_str"].tolist()
    prices = df["current"].tolist()
    volumes = df["volume"].tolist()

    for i in range(len(codes)):
        lookup[(codes[i], dates[i])] = {
            "price": prices[i],
            "volume": volumes[i],
        }
    return lookup


def check_capacity(
    signal: dict[str, Any],
    auction_data: dict[str, float],
) -> dict[str, Any]:
    """Check capacity feasibility for a single signal.

    Returns dict with all required fields per SPEC §3.3.2.
    """
    code = signal["code"]
    side = signal["action"]
    target_qty = signal.get("target_qty", 0)
    target_value = signal.get("target_value", 0)

    auction_price = auction_data.get("price", 0.0)
    auction_volume_shares = auction_data.get("volume", 0.0)
    auction_value = auction_price * auction_volume_shares

    # Compute participation rate
    if auction_volume_shares > 0 and target_qty > 0:
        participation_rate = target_qty / auction_volume_shares
    else:
        participation_rate = 0.0

    # Threshold checks
    threshold_5pct = participation_rate > AUCTION_PARTICIPATION_RATE_LIMIT
    threshold_10pct = participation_rate > 0.10
    threshold_20pct = participation_rate > 0.20

    # Determine executability
    executable = True
    rejection_reason = ""

    # Skip signals (already rejected in backtest)
    if side == "skip":
        executable = False
        rejection_reason = signal.get("rejection_reason", "skip")
    # Sells: no capacity constraint (selling existing position)
    elif side == "sell":
        executable = True
        rejection_reason = ""
    # Buys: apply capacity constraints
    elif side == "buy":
        if auction_volume_shares == 0:
            executable = False
            rejection_reason = "no_auction_data"
        elif auction_volume_shares < MIN_AUCTION_VOLUME_SHARES:
            executable = False
            rejection_reason = f"auction_volume_below_min({int(auction_volume_shares)}<{MIN_AUCTION_VOLUME_SHARES})"
        elif threshold_5pct:
            executable = False
            rejection_reason = f"participation_rate_{participation_rate:.2%}_exceeds_5%"
        else:
            executable = True
            rejection_reason = ""
    else:
        executable = False
        rejection_reason = f"unknown_side_{side}"

    return {
        "code": code,
        "side": side,
        "target_value": target_value,
        "target_qty": target_qty,
        "auction_price_0925": round(auction_price, 4) if auction_price else "",
        "auction_volume_0925": int(auction_volume_shares) if auction_volume_shares else 0,
        "auction_value_0925": round(auction_value, 2) if auction_value else "",
        "participation_rate": round(participation_rate, 6) if participation_rate else 0,
        "threshold_5pct": "Y" if threshold_5pct else "N",
        "threshold_10pct": "Y" if threshold_10pct else "N",
        "threshold_20pct": "Y" if threshold_20pct else "N",
        "executable": "Y" if executable else "N",
        "rejection_reason": rejection_reason,
    }


def process_day(
    date_str: str,
    signals: list[dict[str, Any]],
    auction_lookup: dict[tuple[str, str], dict[str, float]],
) -> list[dict[str, Any]]:
    """Process all signals for a single day."""
    results = []
    for sig in signals:
        key = (sig["code"], date_str)
        auction_data = auction_lookup.get(key, {"price": 0.0, "volume": 0.0})
        result = check_capacity(sig, auction_data)
        result["date"] = date_str
        results.append(result)
    return results


def main() -> None:
    print("=" * 70)
    print("TASK-006E Stage E3: Capacity Checker (degraded mode)")
    print("=" * 70)

    # Load all daily_signal files
    print("\n[1] Loading daily signal files...")
    signal_files = sorted(SIGNALS_DIR.glob("daily_signal_*.csv"))
    # Filter out summary file
    signal_files = [f for f in signal_files if "summary" not in f.name]
    print(f"  Signal files found: {len(signal_files)}")

    if not signal_files:
        print("  ERROR: No signal files found. Run E2 first.")
        sys.exit(1)

    # Group by year for auction data loading
    print("\n[2] Loading call_auction data by year...")
    year_lookups: dict[int, dict] = {}
    all_results: list[dict[str, Any]] = []

    for sf in signal_files:
        # Extract date from filename: daily_signal_YYYYMMDD.csv
        date_compact = sf.stem.replace("daily_signal_", "")
        date_str = f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}"
        year = int(date_compact[:4])

        if year not in year_lookups:
            print(f"  Loading call_auction for {year}...")
            year_lookups[year] = build_auction_lookup(year)
            print(f"    {len(year_lookups[year])} entries loaded")

        # Load signals
        with open(sf, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            signals = list(reader)

        # Convert numeric fields
        for s in signals:
            s["target_qty"] = int(s.get("target_qty", 0) or 0)
            s["target_value"] = float(s.get("target_value", 0) or 0)

        # Process
        day_results = process_day(date_str, signals, year_lookups[year])
        all_results.extend(day_results)

    print(f"\n[3] Processed {len(all_results)} total signals")

    # Write per-day feasibility CSVs
    print("\n[4] Writing per-day feasibility CSVs...")
    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in all_results:
        by_date[r["date"]].append(r)

    fields = [
        "date", "code", "side", "target_value", "target_qty",
        "auction_price_0925", "auction_volume_0925", "auction_value_0925",
        "participation_rate", "threshold_5pct", "threshold_10pct", "threshold_20pct",
        "executable", "rejection_reason",
    ]

    for date_str, rows in by_date.items():
        out_path = OUTPUT_DIR / f"daily_execution_feasibility_{date_str.replace('-', '')}.csv"
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    print(f"  Wrote {len(by_date)} daily feasibility files")

    # Write summary
    print("\n[5] Writing summary...")
    summary_path = OUTPUT_DIR / "capacity_summary.csv"
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "date", "total_signals", "buy_count", "sell_count", "skip_count",
            "executable_count", "rejected_count", "no_auction_data_count",
            "below_min_volume_count", "exceeds_5pct_count",
        ])

        for date_str in sorted(by_date.keys()):
            rows = by_date[date_str]
            total = len(rows)
            side_counter = Counter(r["side"] for r in rows)
            exec_count = sum(1 for r in rows if r["executable"] == "Y")
            rej_count = total - exec_count

            rej_reasons = Counter()
            for r in rows:
                if r["executable"] == "N":
                    reason = r["rejection_reason"]
                    if "no_auction_data" in reason:
                        rej_reasons["no_auction_data"] += 1
                    elif "below_min" in reason:
                        rej_reasons["below_min_volume"] += 1
                    elif "exceeds_5pct" in reason or "5pct" in reason:
                        rej_reasons["exceeds_5pct"] += 1
                    else:
                        rej_reasons["other"] += 1

            writer.writerow([
                date_str, total,
                side_counter.get("buy", 0), side_counter.get("sell", 0), side_counter.get("skip", 0),
                exec_count, rej_count,
                rej_reasons.get("no_auction_data", 0),
                rej_reasons.get("below_min_volume", 0),
                rej_reasons.get("exceeds_5pct", 0),
            ])

    print(f"  -> {summary_path}")

    # Overall stats
    print("\n[6] Overall capacity statistics:")
    total = len(all_results)
    exec_count = sum(1 for r in all_results if r["executable"] == "Y")
    rej_count = total - exec_count

    # Buy-only stats (capacity constraint only applies to buys)
    buy_results = [r for r in all_results if r["side"] == "buy"]
    buy_exec = sum(1 for r in buy_results if r["executable"] == "Y")
    buy_rej = len(buy_results) - buy_exec

    print(f"  Total signals: {total}")
    print(f"  Total executable: {exec_count} ({exec_count/total*100:.1f}%)")
    print(f"  Total rejected: {rej_count} ({rej_count/total*100:.1f}%)")
    print(f"  Buy signals: {len(buy_results)}")
    print(f"  Buy executable: {buy_exec} ({buy_exec/len(buy_results)*100:.1f}% of buys)" if buy_results else "  Buy executable: 0")
    print(f"  Buy rejected: {buy_rej} ({buy_rej/len(buy_results)*100:.1f}% of buys)" if buy_results else "  Buy rejected: 0")

    # Rejection reason distribution
    print("\n  Rejection reason distribution (buys only):")
    buy_rej_reasons = Counter()
    for r in buy_results:
        if r["executable"] == "N":
            reason = r["rejection_reason"]
            if "no_auction_data" in reason:
                buy_rej_reasons["no_auction_data"] += 1
            elif "below_min" in reason:
                buy_rej_reasons["below_min_volume"] += 1
            elif "exceeds" in reason or "5%" in reason:
                buy_rej_reasons["exceeds_5pct"] += 1
            else:
                buy_rej_reasons["other"] += 1
    for reason, count in buy_rej_reasons.most_common():
        print(f"    {reason}: {count}")

    print("\n[E3] Done.")


if __name__ == "__main__":
    main()
