#!/usr/bin/env python3
"""
TASK-006G-R1 Stage 7: Difference Attribution
==============================================
Attribute differences between JQ master and local backtest to categories.

Inputs:
- outputs/TRADE_RECON_2025.csv
- outputs/EQUITY_RECON_2025.csv
- outputs/TRADE_RECON_2026_FRAGMENT.csv
- outputs/EQUITY_RECON_2026_FRAGMENT.csv

Outputs:
- outputs/DIFF_ATTRIBUTION_2025.csv + DIFF_ATTRIBUTION_2025.md
- outputs/DIFF_ATTRIBUTION_2026_FRAGMENT.csv + DIFF_ATTRIBUTION_2026_FRAGMENT.md

Attribution categories:
- start_state_mismatch
- jq_qty_zero_export_defect
- trade_price_diff
- trade_quantity_diff
- fee_diff
- tax_diff
- data_source_price_diff
- market_cap_rank_diff
- call_auction_diff
- limit_status_diff
- suspension_status_diff
- st_status_diff
- rounding_lot_size
- cash_rounding
- cascade_residual
- unknown
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(r"D:\Work Space\他山之石\微盘股")
OUTPUT_DIR = PROJECT_ROOT / "research" / "local_port_v0" / "task_006g_r1_local_strict_reconcile" / "outputs"


def _classify_trade_diff(row):
    """Classify a trade recon row into attribution category."""
    status = row.get("match_status", "")
    reason = row.get("diff_reason", "")
    if status == "exact_match":
        return None  # no diff
    if status == "qty_zero_export_defect" or reason == "jq_qty_zero_export_defect":
        return "jq_qty_zero_export_defect"
    if status == "quantity_diff":
        if "lot_rounding" in reason or "rounding" in reason:
            return "rounding_lot_size"
        return "trade_quantity_diff"
    if status == "price_diff":
        if "hdata_minute_close_diff" in reason:
            return "data_source_price_diff"
        return "trade_price_diff"
    if status == "price_and_quantity_diff":
        return "trade_price_diff"
    if status == "missing_in_local":
        return "cascade_residual"
    if status == "missing_in_jq":
        return "cascade_residual"
    return "unknown"


def _classify_equity_diff(row):
    """Classify an equity recon row into attribution category."""
    status = row.get("match_status", "")
    if status in ("exact_match", "no_data"):
        return None
    if status in ("missing_in_local", "missing_in_jq"):
        return "start_state_mismatch"
    if status == "small_diff":
        return "cash_rounding"
    if status == "large_diff":
        return "cascade_residual"
    return "unknown"


def attribute_diffs(trade_recon_path, equity_recon_path, period_label):
    """Attribute differences from trade and equity recon files."""
    attributions = defaultdict(lambda: {
        "count": 0, "first_date": "", "last_date": "",
        "sum_asset_impact": 0.0, "max_single_day_impact": 0.0,
        "evidence_level": "B", "is_real_difference": False, "notes": "",
    })

    # Trade recon
    if trade_recon_path and trade_recon_path.exists():
        df = pd.read_csv(trade_recon_path)
        for _, r in df.iterrows():
            cat = _classify_trade_diff(r)
            if cat is None:
                continue
            a = attributions[cat]
            a["count"] += 1
            d = str(r.get("date", ""))
            if not a["first_date"] or d < a["first_date"]:
                a["first_date"] = d
            if not a["last_date"] or d > a["last_date"]:
                a["last_date"] = d
            # Asset impact: use gross_amount_diff as proxy
            impact = abs(float(r.get("gross_amount_diff", 0) or 0))
            a["sum_asset_impact"] += impact
            if impact > a["max_single_day_impact"]:
                a["max_single_day_impact"] = impact
            # Real difference flags
            if cat == "jq_qty_zero_export_defect":
                a["is_real_difference"] = False
                a["notes"] = "JQ export defect, not a real strategy difference"
            elif cat in ("trade_price_diff", "trade_quantity_diff", "data_source_price_diff"):
                a["is_real_difference"] = True
                a["evidence_level"] = "A"
            elif cat == "cascade_residual":
                a["is_real_difference"] = True
                a["evidence_level"] = "B"
                a["notes"] = "Cascade after first divergence"
            elif cat == "rounding_lot_size":
                a["is_real_difference"] = False
                a["notes"] = "Lot size rounding, mechanical"

    # Equity recon
    if equity_recon_path and equity_recon_path.exists():
        df = pd.read_csv(equity_recon_path)
        for _, r in df.iterrows():
            cat = _classify_equity_diff(r)
            if cat is None:
                continue
            a = attributions[cat]
            a["count"] += 1
            d = str(r.get("date", ""))
            if not a["first_date"] or d < a["first_date"]:
                a["first_date"] = d
            if not a["last_date"] or d > a["last_date"]:
                a["last_date"] = d
            impact = abs(float(r.get("asset_diff", 0) or 0))
            a["sum_asset_impact"] += impact
            if impact > a["max_single_day_impact"]:
                a["max_single_day_impact"] = impact
            if cat == "cascade_residual":
                a["is_real_difference"] = True
                a["evidence_level"] = "B"
            elif cat == "cash_rounding":
                a["is_real_difference"] = False
                a["notes"] = "Small diff < 1000, likely rounding"

    return attributions


ATTR_FIELDS = [
    "category", "count", "first_date", "last_date",
    "sum_asset_impact", "max_single_day_impact",
    "evidence_level", "is_real_difference", "notes",
]


def write_attribution_csv(attributions, out_path, period_label):
    rows = []
    for cat, a in sorted(attributions.items()):
        rows.append({
            "category": cat,
            "count": a["count"],
            "first_date": a["first_date"],
            "last_date": a["last_date"],
            "sum_asset_impact": round(a["sum_asset_impact"], 2),
            "max_single_day_impact": round(a["max_single_day_impact"], 2),
            "evidence_level": a["evidence_level"],
            "is_real_difference": a["is_real_difference"],
            "notes": a["notes"],
        })
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ATTR_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote: {out_path}  ({len(rows)} categories)")
    return rows


def write_attribution_md(rows, out_path, period_label):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# TASK-006G-R1 Difference Attribution: {period_label}\n\n")
        f.write(f"## Attribution Matrix\n\n")
        f.write("| Category | Count | First Date | Last Date | Sum Impact | Max Impact | Evidence | Real? | Notes |\n")
        f.write("|----------|-------|------------|-----------|------------|------------|----------|-------|-------|\n")
        for r in rows:
            f.write(f"| {r['category']} | {r['count']} | {r['first_date']} | {r['last_date']} | "
                    f"{r['sum_asset_impact']} | {r['max_single_day_impact']} | "
                    f"{r['evidence_level']} | {r['is_real_difference']} | {r['notes']} |\n")
        f.write("\n## Key Findings\n\n")
        real_diffs = [r for r in rows if r["is_real_difference"]]
        export_defects = [r for r in rows if r["category"] == "jq_qty_zero_export_defect"]
        f.write(f"- Real differences: {sum(r['count'] for r in real_diffs)} events across {len(real_diffs)} categories\n")
        f.write(f"- Export defects: {sum(r['count'] for r in export_defects)} events (not real strategy differences)\n")
    print(f"Wrote: {out_path}")


def main():
    print("=" * 70)
    print("TASK-006G-R1 Stage 7: Difference Attribution")
    print("=" * 70)

    # ---- 2025 ----
    print("\n[1/2] 2025 difference attribution...")
    trade_path = OUTPUT_DIR / "TRADE_RECON_2025.csv"
    equity_path = OUTPUT_DIR / "EQUITY_RECON_2025.csv"
    attributions = attribute_diffs(
        trade_path if trade_path.exists() else None,
        equity_path if equity_path.exists() else None,
        "2025")
    rows = write_attribution_csv(attributions, OUTPUT_DIR / "DIFF_ATTRIBUTION_2025.csv", "2025")
    write_attribution_md(rows, OUTPUT_DIR.parent / "DIFF_ATTRIBUTION_2025.md", "2025")
    for r in rows:
        print(f"  {r['category']}: count={r['count']}, real={r['is_real_difference']}")

    # ---- 2026 fragment ----
    print("\n[2/2] 2026 fragment difference attribution...")
    trade_path = OUTPUT_DIR / "TRADE_RECON_2026_FRAGMENT.csv"
    equity_path = OUTPUT_DIR / "EQUITY_RECON_2026_FRAGMENT.csv"
    attributions = attribute_diffs(
        trade_path if trade_path.exists() else None,
        equity_path if equity_path.exists() else None,
        "2026 fragment")
    rows = write_attribution_csv(attributions, OUTPUT_DIR / "DIFF_ATTRIBUTION_2026_FRAGMENT.csv", "2026 fragment")
    write_attribution_md(rows, OUTPUT_DIR.parent / "DIFF_ATTRIBUTION_2026_FRAGMENT.md", "2026 fragment")
    for r in rows:
        print(f"  {r['category']}: count={r['count']}, real={r['is_real_difference']}")

    print("\n=== Difference Attribution Complete ===")


if __name__ == "__main__":
    main()
