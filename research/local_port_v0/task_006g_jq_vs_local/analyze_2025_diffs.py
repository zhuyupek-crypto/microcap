#!/usr/bin/env python3
"""TASK-006G Stage 3: Detailed diff distribution analysis for 2025 trade match."""
from __future__ import annotations

import csv
from collections import defaultdict, Counter
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent
TRADE_MATCH_CSV = OUTPUT_DIR / "JQ_LOCAL_2025_TRADE_MATCH.csv"


def main() -> None:
    rows = []
    with open(TRADE_MATCH_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"Total rows: {len(rows)}")

    # Status counts
    status_counts = Counter(r["match_status"] for r in rows)
    print("\n=== Status counts ===")
    for s, c in sorted(status_counts.items()):
        print(f"  {s}: {c}")

    # Amount diff distribution (only for amount_diff and price_and_amount_diff)
    amount_diffs = []
    for r in rows:
        if r["match_status"] in ("amount_diff", "price_and_amount_diff"):
            try:
                d = int(r["amount_diff"])
                amount_diffs.append(d)
            except (ValueError, TypeError):
                pass

    print(f"\n=== Amount diff distribution (n={len(amount_diffs)}) ===")
    if amount_diffs:
        abs_diffs = [abs(d) for d in amount_diffs]
        mean = sum(abs_diffs) / len(abs_diffs)
        max_d = max(abs_diffs)
        min_d = min(abs_diffs)
        print(f"  Mean |diff|: {mean:.1f}")
        print(f"  Max |diff|: {max_d}")
        print(f"  Min |diff|: {min_d}")
        buckets = {"<=100": 0, "101-500": 0, "501-1000": 0, "1001-5000": 0, ">5000": 0}
        for d in abs_diffs:
            if d <= 100:
                buckets["<=100"] += 1
            elif d <= 500:
                buckets["101-500"] += 1
            elif d <= 1000:
                buckets["501-1000"] += 1
            elif d <= 5000:
                buckets["1001-5000"] += 1
            else:
                buckets[">5000"] += 1
        for b, c in buckets.items():
            print(f"  {b}: {c}")

        # Direction (local - jq): positive = local sells more / buys more
        pos = sum(1 for d in amount_diffs if d > 0)
        neg = sum(1 for d in amount_diffs if d < 0)
        print(f"  Local > JQ (positive diff): {pos}")
        print(f"  Local < JQ (negative diff): {neg}")

    # Distinguish JQ qty=0 export defect vs real amount diff
    print("\n=== JQ qty=0 export defect vs real amount diff ===")
    jq_zero_defect = 0  # JQ qty=0, local has qty (清仓 sell export defect)
    real_diff = 0
    real_diff_samples = []
    for r in rows:
        if r["match_status"] in ("amount_diff", "price_and_amount_diff"):
            try:
                jq_amt = int(r["jq_amount"]) if r["jq_amount"] else 0
                loc_amt = int(r["local_amount"]) if r["local_amount"] else 0
                if jq_amt == 0 and loc_amt > 0:
                    jq_zero_defect += 1
                elif jq_amt > 0 and loc_amt > 0:
                    real_diff += 1
                    if len(real_diff_samples) < 20:
                        real_diff_samples.append(
                            f"  {r['date']} {r['code']} {r['side']} jq={jq_amt} local={loc_amt} diff={loc_amt-jq_amt}"
                        )
            except (ValueError, TypeError):
                pass
    print(f"  JQ qty=0 export defect (清仓 sell): {jq_zero_defect}")
    print(f"  Real quantity diff (both non-zero): {real_diff}")
    print("  Real diff samples:")
    for s in real_diff_samples:
        print(s)

    # Side breakdown for amount_diff
    side_status = defaultdict(lambda: defaultdict(int))
    for r in rows:
        side_status[r["side"]][r["match_status"]] += 1
    print("\n=== Side x Status breakdown ===")
    for side in sorted(side_status.keys()):
        print(f"  {side}:")
        for s, c in sorted(side_status[side].items()):
            print(f"    {s}: {c}")

    # Price diff analysis
    price_diffs = []
    for r in rows:
        if r["match_status"] in ("price_diff", "price_and_amount_diff"):
            try:
                d = float(r["price_diff"])
                price_diffs.append(d)
            except (ValueError, TypeError):
                pass

    print(f"\n=== Price diff distribution (n={len(price_diffs)}) ===")
    if price_diffs:
        abs_diffs = [abs(d) for d in price_diffs]
        mean = sum(abs_diffs) / len(abs_diffs)
        max_d = max(abs_diffs)
        min_d = min(abs_diffs)
        print(f"  Mean |price_diff|: {mean:.4f}")
        print(f"  Max |price_diff|: {max_d:.4f}")
        print(f"  Min |price_diff|: {min_d:.4f}")
        # List each
        print("  Per-trade details:")
        for r in rows:
            if r["match_status"] in ("price_diff", "price_and_amount_diff"):
                try:
                    d = float(r["price_diff"])
                    print(f"    {r['date']} {r['code']} {r['side']} jq={r['jq_price']} local={r['local_price']} diff={d:.4f}")
                except (ValueError, TypeError):
                    pass

    # Missing in local
    missing_local = [r for r in rows if r["match_status"] == "missing_in_local"]
    print(f"\n=== Missing in local (n={len(missing_local)}) ===")
    for r in missing_local:
        print(f"  {r['date']} {r['code']} {r['side']} jq_amount={r['jq_amount']} jq_price={r['jq_price']}")

    # Missing in JQ
    missing_jq = [r for r in rows if r["match_status"] == "missing_in_jq"]
    print(f"\n=== Missing in JQ (n={len(missing_jq)}) ===")
    for r in missing_jq:
        print(f"  {r['date']} {r['code']} {r['side']} local_amount={r['local_amount']} local_price={r['local_price']}")

    # Commission diff
    comm_diffs = []
    for r in rows:
        if r["match_status"] in ("amount_diff", "price_and_amount_diff"):
            try:
                d = float(r["commission_diff"])
                comm_diffs.append(d)
            except (ValueError, TypeError):
                pass
    print(f"\n=== Commission diff (n={len(comm_diffs)}) ===")
    if comm_diffs:
        print(f"  Mean: {sum(comm_diffs)/len(comm_diffs):.4f}")
        print(f"  Min: {min(comm_diffs):.4f}")
        print(f"  Max: {max(comm_diffs):.4f}")
        # All negative? (JQ commission > local because JQ has actual qty, local min 5)
        neg = sum(1 for d in comm_diffs if d < 0)
        zero = sum(1 for d in comm_diffs if d == 0)
        pos = sum(1 for d in comm_diffs if d > 0)
        print(f"  negative (JQ>local): {neg}, zero: {zero}, positive (local>JQ): {pos}")

    # Monthly distribution
    print("\n=== Monthly match status ===")
    monthly = defaultdict(lambda: defaultdict(int))
    for r in rows:
        month = r["date"][:7]
        monthly[month][r["match_status"]] += 1
    for m in sorted(monthly.keys()):
        total = sum(monthly[m].values())
        exact = monthly[m].get("exact_match", 0)
        rate = exact / total * 100 if total else 0
        print(f"  {m}: total={total} exact={exact} ({rate:.1f}%)")
        for s, c in sorted(monthly[m].items()):
            if s != "exact_match":
                print(f"    {s}: {c}")


if __name__ == "__main__":
    main()
