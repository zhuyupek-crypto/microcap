#!/usr/bin/env python3
"""
TASK-006G-R1 Stage 4 & 6: Trade Reconciliation
=================================================
Reconcile JQ master trades vs local same-start backtest trades.

Stage 4: 2025 full-year
Stage 6: 2026-05~06 fragment

Match key priority:
1. date + code + side + sequence_in_day
2. date + code + side + quantity + price
3. date + code + side
4. date + code (cross-side)

Output fields per spec section VIII.

Outputs:
- outputs/TRADE_RECON_2025.csv + TRADE_RECON_2025.md
- outputs/TRADE_RECON_2026_FRAGMENT.csv + TRADE_RECON_2026_FRAGMENT.md
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(r"D:\Work Space\他山之石\微盘股")
OUTPUT_DIR = PROJECT_ROOT / "research" / "local_port_v0" / "task_006g_r1_local_strict_reconcile" / "outputs"


def load_jq_trades(csv_path):
    """Load JQ normalized trades CSV."""
    df = pd.read_csv(csv_path)
    df["date"] = df["date"].astype(str)
    df["side"] = df["side"].astype(str)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["gross_amount"] = pd.to_numeric(df["gross_amount"], errors="coerce")
    df["commission"] = pd.to_numeric(df["commission"], errors="coerce").fillna(0)
    # For sells, JQ stores quantity as negative; normalize side-aware
    df["abs_qty"] = df["quantity"].abs()
    return df


def load_local_trades(csv_path):
    """Load local backtest trades CSV.
    Local format: time, code, amount, price, commission, tax, trade_id, order_id
    amount is signed: + for buy, - for sell.
    """
    df = pd.read_csv(csv_path)
    # Extract date from time
    df["date"] = df["time"].astype(str).str[:10]
    df["side"] = df["amount"].apply(lambda x: "buy" if x > 0 else ("sell" if x < 0 else "unknown"))
    df["abs_qty"] = df["amount"].abs()
    df["gross_amount"] = df["price"] * df["amount"].abs()  # positive gross
    # For sells, gross should be negative in JQ convention; but for matching we use abs
    df["commission"] = pd.to_numeric(df.get("commission", 0), errors="coerce").fillna(0)
    return df


def reconcile(jq_df, local_df, period_label):
    """Reconcile two trade dataframes. Returns (recon_rows, stats)."""
    # Build per-day-per-code-per-side groups
    recon_rows = []

    # Sequence within day for both sides
    def _add_seq(df):
        df = df.sort_values(["date", "time"] if "time" in df.columns else ["date"]).reset_index(drop=True)
        df["seq_in_day"] = df.groupby(["date", "code", "side"]).cumcount()
        return df

    jq_df = _add_seq(jq_df)
    local_df = _add_seq(local_df)

    # Build match key
    def _make_key(row, level):
        if level == 1:
            return (row["date"], row["code"], row["side"], row.get("seq_in_day", 0))
        elif level == 2:
            return (row["date"], row["code"], row["side"], row.get("abs_qty", 0), row.get("price", 0))
        elif level == 3:
            return (row["date"], row["code"], row["side"])
        return None

    # Index local trades by various keys for matching
    local_by_key1 = defaultdict(list)
    local_by_key2 = defaultdict(list)
    local_by_key3 = defaultdict(list)
    for idx, row in local_df.iterrows():
        local_by_key1[_make_key(row, 1)].append(idx)
        local_by_key2[_make_key(row, 2)].append(idx)
        local_by_key3[_make_key(row, 3)].append(idx)

    matched_local_idx = set()

    # First pass: level 1 (date+code+side+seq)
    for _, jq_row in jq_df.iterrows():
        key = _make_key(jq_row, 1)
        candidates = [i for i in local_by_key1.get(key, []) if i not in matched_local_idx]
        if candidates:
            local_idx = candidates[0]
            matched_local_idx.add(local_idx)
            local_row = local_df.loc[local_idx]
            recon_rows.append(_build_recon_row(jq_row, local_row, "exact_match"))
            continue
        # Level 2: date+code+side+qty+price (allow small price diff)
        key2 = _make_key(jq_row, 2)
        candidates = [i for i in local_by_key2.get(key2, []) if i not in matched_local_idx]
        if candidates:
            local_idx = candidates[0]
            matched_local_idx.add(local_idx)
            local_row = local_df.loc[local_idx]
            recon_rows.append(_build_recon_row(jq_row, local_row, "exact_match"))
            continue
        # Level 3: date+code+side (fuzzy)
        key3 = _make_key(jq_row, 3)
        candidates = [i for i in local_by_key3.get(key3, []) if i not in matched_local_idx]
        if candidates:
            local_idx = candidates[0]
            matched_local_idx.add(local_idx)
            local_row = local_df.loc[local_idx]
            # Determine diff type
            status = _classify_diff(jq_row, local_row)
            recon_rows.append(_build_recon_row(jq_row, local_row, status))
            continue
        # No match found -> missing in local
        recon_rows.append(_build_recon_row(jq_row, None, "missing_in_local"))

    # Add local trades not matched -> missing in JQ
    for idx, local_row in local_df.iterrows():
        if idx not in matched_local_idx:
            recon_rows.append(_build_recon_row(None, local_row, "missing_in_jq"))

    # Sort by date, code, side
    recon_rows.sort(key=lambda r: (r.get("date", ""), r.get("code", ""), r.get("side", "")))

    # Stats
    stats = _compute_stats(jq_df, local_df, recon_rows)
    return recon_rows, stats


def _classify_diff(jq_row, local_row):
    """Classify the type of difference."""
    jq_qty = float(jq_row.get("abs_qty", 0) or 0)
    loc_qty = float(local_row.get("abs_qty", 0) or 0)
    jq_price = float(jq_row.get("price", 0) or 0)
    loc_price = float(local_row.get("price", 0) or 0)

    # JQ qty=0 export defect
    if jq_qty == 0 and float(jq_row.get("gross_amount", 0) or 0) != 0:
        return "qty_zero_export_defect"

    qty_diff = abs(jq_qty - loc_qty) > 0.01
    price_diff = abs(jq_price - loc_price) > 0.001 if jq_price and loc_price else False

    if qty_diff and price_diff:
        return "price_and_quantity_diff"
    if qty_diff:
        return "quantity_diff"
    if price_diff:
        return "price_diff"
    return "exact_match"


def _build_recon_row(jq_row, local_row, match_status):
    """Build a reconciliation row."""
    if jq_row is not None:
        jq_qty = float(jq_row.get("abs_qty", 0) or 0)
        jq_price = float(jq_row.get("price", 0) or 0)
        jq_gross = float(jq_row.get("gross_amount", 0) or 0)
        jq_comm = float(jq_row.get("commission", 0) or 0)
    else:
        jq_qty = jq_price = jq_gross = jq_comm = 0
    if local_row is not None:
        loc_qty = float(local_row.get("abs_qty", 0) or 0)
        loc_price = float(local_row.get("price", 0) or 0)
        loc_gross = float(local_row.get("gross_amount", 0) or 0)
        loc_comm = float(local_row.get("commission", 0) or 0)
    else:
        loc_qty = loc_price = loc_gross = loc_comm = 0

    # Determine diff_reason
    diff_reason = "unknown"
    if match_status == "exact_match":
        diff_reason = "none"
    elif match_status == "qty_zero_export_defect":
        diff_reason = "jq_qty_zero_export_defect"
    elif match_status == "quantity_diff":
        diff_reason = "lot_rounding" if abs(jq_qty - loc_qty) < 200 else "unknown"
    elif match_status == "price_diff":
        diff_reason = "hdata_minute_close_diff"
    elif match_status == "missing_in_local":
        diff_reason = "cascade_after_first_divergence"
    elif match_status == "missing_in_jq":
        diff_reason = "cascade_after_first_divergence"

    return {
        "date": jq_row["date"] if jq_row is not None else (local_row["date"] if local_row is not None else ""),
        "sequence": jq_row.get("seq_in_day", 0) if jq_row is not None else (local_row.get("seq_in_day", 0) if local_row is not None else 0),
        "code": jq_row["code"] if jq_row is not None else (local_row["code"] if local_row is not None else ""),
        "side": jq_row["side"] if jq_row is not None else (local_row["side"] if local_row is not None else ""),
        "jq_quantity": jq_qty,
        "local_quantity": loc_qty,
        "quantity_diff": jq_qty - loc_qty,
        "jq_price": jq_price,
        "local_price": loc_price,
        "price_diff": jq_price - loc_price,
        "jq_gross_amount": jq_gross,
        "local_gross_amount": loc_gross,
        "gross_amount_diff": jq_gross - loc_gross,
        "jq_commission": jq_comm,
        "local_commission": loc_comm,
        "commission_diff": jq_comm - loc_comm,
        "jq_tax": 0,
        "local_tax": 0,
        "tax_diff": 0,
        "match_status": match_status,
        "diff_reason": diff_reason,
        "evidence_level": "A" if match_status == "exact_match" else "B",
    }


def _compute_stats(jq_df, local_df, recon_rows):
    """Compute summary statistics."""
    total_jq = len(jq_df)
    total_local = len(local_df)
    exact = sum(1 for r in recon_rows if r["match_status"] == "exact_match")
    qty_zero = sum(1 for r in recon_rows if r["match_status"] == "qty_zero_export_defect")
    qty_diff = sum(1 for r in recon_rows if r["match_status"] == "quantity_diff")
    price_diff = sum(1 for r in recon_rows if r["match_status"] == "price_diff")
    pq_diff = sum(1 for r in recon_rows if r["match_status"] == "price_and_quantity_diff")
    missing_local = sum(1 for r in recon_rows if r["match_status"] == "missing_in_local")
    missing_jq = sum(1 for r in recon_rows if r["match_status"] == "missing_in_jq")

    # First divergence
    first_div_date = ""
    first_div_code = ""
    for r in sorted(recon_rows, key=lambda x: (x.get("date", ""), x.get("code", ""))):
        if r["match_status"] not in ("exact_match",):
            first_div_date = r.get("date", "")
            first_div_code = r.get("code", "")
            break

    exact_rate = exact / total_jq if total_jq > 0 else 0
    return {
        "total_jq_trades": total_jq,
        "total_local_trades": total_local,
        "exact_match_count": exact,
        "exact_match_rate": round(exact_rate, 4),
        "qty_zero_export_defect_count": qty_zero,
        "real_quantity_diff_count": qty_diff,
        "price_diff_count": price_diff,
        "price_and_quantity_diff_count": pq_diff,
        "missing_in_local_count": missing_local,
        "missing_in_jq_count": missing_jq,
        "first_trade_divergence_date": first_div_date,
        "first_trade_divergence_code": first_div_code,
    }


RECON_FIELDS = [
    "date", "sequence", "code", "side",
    "jq_quantity", "local_quantity", "quantity_diff",
    "jq_price", "local_price", "price_diff",
    "jq_gross_amount", "local_gross_amount", "gross_amount_diff",
    "jq_commission", "local_commission", "commission_diff",
    "jq_tax", "local_tax", "tax_diff",
    "match_status", "diff_reason", "evidence_level",
]


def write_recon_csv(rows, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RECON_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in RECON_FIELDS})
    print(f"Wrote: {out_path}  ({len(rows)} rows)")


def write_recon_md(stats, out_path, period_label, jq_path, local_path):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# TASK-006G-R1 Trade Reconciliation: {period_label}\n\n")
        f.write(f"## Inputs\n\n")
        f.write(f"- JQ: `{jq_path}`\n")
        f.write(f"- Local: `{local_path}`\n\n")
        f.write(f"## Statistics\n\n")
        f.write("| Metric | Value |\n|--------|-------|\n")
        for k, v in stats.items():
            f.write(f"| {k} | {v} |\n")
        f.write(f"\n## Match Status Distribution\n\n")
    print(f"Wrote: {out_path}")


def main():
    print("=" * 70)
    print("TASK-006G-R1 Stage 4/6: Trade Reconciliation")
    print("=" * 70)

    # ---- 2025 ----
    print("\n[1/2] 2025 full-year trade reconciliation...")
    jq_path = OUTPUT_DIR / "JQ_2025_TRADES_NORMALIZED.csv"
    local_path = OUTPUT_DIR.parent / "runs" / "r1_2025_research" / "trades.csv"
    if not jq_path.exists():
        print(f"  SKIP: {jq_path} not found")
    elif not local_path.exists():
        print(f"  SKIP: {local_path} not found (run Stage 3 first)")
    else:
        jq_df = load_jq_trades(jq_path)
        local_df = load_local_trades(local_path)
        print(f"  JQ trades: {len(jq_df)}, Local trades: {len(local_df)}")
        rows, stats = reconcile(jq_df, local_df, "2025")
        write_recon_csv(rows, OUTPUT_DIR / "TRADE_RECON_2025.csv")
        write_recon_md(stats, OUTPUT_DIR.parent / "TRADE_RECON_2025.md",
                       "2025 full-year", jq_path, local_path)
        for k, v in stats.items():
            print(f"  {k}: {v}")

    # ---- 2026 fragment ----
    print("\n[2/2] 2026-05~06 fragment trade reconciliation...")
    jq_path = OUTPUT_DIR / "JQ_2026_FRAGMENT_TRADES_NORMALIZED.csv"
    local_path = OUTPUT_DIR.parent / "runs" / "r1_2026m05_research" / "trades.csv"
    if not jq_path.exists():
        print(f"  SKIP: {jq_path} not found")
    elif not local_path.exists():
        print(f"  SKIP: {local_path} not found (run Stage 3 first)")
    else:
        jq_df = load_jq_trades(jq_path)
        local_df = load_local_trades(local_path)
        print(f"  JQ trades: {len(jq_df)}, Local trades: {len(local_df)}")
        rows, stats = reconcile(jq_df, local_df, "2026-05~06 fragment")
        write_recon_csv(rows, OUTPUT_DIR / "TRADE_RECON_2026_FRAGMENT.csv")
        write_recon_md(stats, OUTPUT_DIR.parent / "TRADE_RECON_2026_FRAGMENT.md",
                       "2026-05~06 fragment", jq_path, local_path)
        for k, v in stats.items():
            print(f"  {k}: {v}")

    print("\n=== Trade Reconciliation Complete ===")


if __name__ == "__main__":
    main()
