#!/usr/bin/env python3
"""
TASK-006G-R1 Stage 5 & 6: Equity / Net-Value Reconciliation
=============================================================
Reconcile JQ master portfolio/equity vs local same-start backtest equity.

Stage 5: 2025 (H1 only for equity; full-year trade recon is separate)
Stage 6: 2026-05~06 fragment

Outputs:
- outputs/EQUITY_RECON_2025.csv + EQUITY_RECON_2025.md
- outputs/EQUITY_RECON_2026_FRAGMENT.csv + EQUITY_RECON_2026_FRAGMENT.md

Note: 2025 JQ equity records only cover H1 (2025-01-02 ~ 2025-06-19).
Full-year A-level equity reconciliation is NOT possible; will downgrade
to H1 A/B + full-year C.
"""
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(r"D:\Work Space\他山之石\微盘股")
OUTPUT_DIR = PROJECT_ROOT / "research" / "local_port_v0" / "task_006g_r1_local_strict_reconcile" / "outputs"


def load_jq_equity(csv_path):
    """Load JQ normalized equity CSV (account-level rows only).
    Detects and marks truncated days (where position_count drops abruptly
    and cash is missing, indicating incomplete JQ export).
    """
    df = pd.read_csv(csv_path)
    df = df[df["snapshot_type"] == "account"].copy()
    df["date"] = df["date"].astype(str)
    df["total_asset"] = pd.to_numeric(df["total_asset"], errors="coerce")
    df["cash"] = pd.to_numeric(df["cash"], errors="coerce")
    df["position_market_value_reported"] = pd.to_numeric(
        df["position_market_value_reported"], errors="coerce").fillna(0)
    df["position_count"] = pd.to_numeric(df["position_count"], errors="coerce").fillna(0).astype(int)
    df = df.sort_values("date").reset_index(drop=True)
    # Detect truncated days: position_count drops >50% from prior day AND cash is NaN
    df["is_truncated"] = False
    for i in range(1, len(df)):
        prev_count = df.loc[i-1, "position_count"]
        cur_count = df.loc[i, "position_count"]
        cur_cash_nan = pd.isna(df.loc[i, "cash"])
        if prev_count > 0 and cur_count < prev_count * 0.5 and cur_cash_nan:
            df.loc[i, "is_truncated"] = True
    truncated_dates = df[df["is_truncated"]]["date"].tolist()
    if truncated_dates:
        print(f"  WARNING: Detected {len(truncated_dates)} truncated JQ equity day(s): {truncated_dates}")
        print(f"  These will be excluded from reconciliation stats.")
        df = df[~df["is_truncated"]].copy()
    return df


def load_local_equity(csv_path):
    """Load local backtest equity CSV.
    Format: date, value
    """
    df = pd.read_csv(csv_path)
    df["date"] = df["date"].astype(str)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    # Local equity.csv only has total value; cash and positions_value not in this file.
    # We'll need to get those from manifest or compute from trades.
    df = df.sort_values("date").reset_index(drop=True)
    return df


def reconcile_equity(jq_df, local_df, period_label, jq_start_asset=None, local_start_asset=None):
    """Reconcile two equity curves. Returns (recon_rows, stats)."""
    # Merge on date
    merged = pd.merge(jq_df[["date", "total_asset", "cash", "position_market_value_reported", "position_count"]],
                      local_df[["date", "value"]],
                      on="date", how="outer", suffixes=("_jq", "_local"))
    merged = merged.sort_values("date").reset_index(drop=True)

    # Rename
    merged["jq_total_asset"] = merged["total_asset"]
    merged["local_total_asset"] = merged["value"]
    merged["jq_cash"] = merged["cash"]
    merged["local_cash"] = np.nan  # not available in local equity.csv
    merged["jq_position_value"] = merged["position_market_value_reported"]
    merged["local_position_value"] = np.nan
    merged["jq_position_count"] = merged["position_count"]
    merged["local_position_count"] = np.nan

    # Compute diffs
    merged["asset_diff"] = merged["jq_total_asset"] - merged["local_total_asset"]
    merged["asset_diff_pct"] = np.where(
        merged["local_total_asset"].notna() & (merged["local_total_asset"] != 0),
        merged["asset_diff"] / merged["local_total_asset"], np.nan)
    merged["cash_diff"] = merged["jq_cash"] - merged["local_cash"]
    merged["position_value_diff"] = merged["jq_position_value"] - merged["local_position_value"]
    merged["position_count_diff"] = merged["jq_position_count"] - merged["local_position_count"]

    # Daily returns
    merged["jq_daily_return"] = merged["jq_total_asset"].pct_change()
    merged["local_daily_return"] = merged["local_total_asset"].pct_change()
    merged["daily_return_diff"] = merged["jq_daily_return"] - merged["local_daily_return"]

    # Cum returns
    if jq_start_asset is None:
        jq_start_asset = merged["jq_total_asset"].dropna().iloc[0] if not merged["jq_total_asset"].dropna().empty else 1_000_000
    if local_start_asset is None:
        local_start_asset = merged["local_total_asset"].dropna().iloc[0] if not merged["local_total_asset"].dropna().empty else 1_000_000
    merged["jq_cum_return"] = merged["jq_total_asset"] / jq_start_asset - 1
    merged["local_cum_return"] = merged["local_total_asset"] / local_start_asset - 1
    merged["cum_return_diff"] = merged["jq_cum_return"] - merged["local_cum_return"]

    # Match status
    def _status(row):
        if pd.isna(row["jq_total_asset"]) and pd.isna(row["local_total_asset"]):
            return "no_data"
        if pd.isna(row["jq_total_asset"]):
            return "missing_in_jq"
        if pd.isna(row["local_total_asset"]):
            return "missing_in_local"
        diff = abs(row["asset_diff"])
        if diff < 1.0:
            return "exact_match"
        if diff < 1000:
            return "small_diff"
        return "large_diff"
    merged["match_status"] = merged.apply(_status, axis=1)
    merged["diff_reason"] = merged["match_status"].apply(
        lambda x: "none" if x == "exact_match" else (
            "start_state_mismatch" if x == "no_data" else "cascade_residual"))

    # Build recon rows
    recon_rows = []
    for _, r in merged.iterrows():
        recon_rows.append({
            "date": r["date"],
            "jq_total_asset": r["jq_total_asset"] if pd.notna(r["jq_total_asset"]) else "",
            "local_total_asset": r["local_total_asset"] if pd.notna(r["local_total_asset"]) else "",
            "asset_diff": r["asset_diff"] if pd.notna(r["asset_diff"]) else "",
            "asset_diff_pct": r["asset_diff_pct"] if pd.notna(r["asset_diff_pct"]) else "",
            "jq_cash": r["jq_cash"] if pd.notna(r["jq_cash"]) else "",
            "local_cash": r["local_cash"] if pd.notna(r["local_cash"]) else "",
            "cash_diff": r["cash_diff"] if pd.notna(r["cash_diff"]) else "",
            "jq_position_value": r["jq_position_value"] if pd.notna(r["jq_position_value"]) else "",
            "local_position_value": r["local_position_value"] if pd.notna(r["local_position_value"]) else "",
            "position_value_diff": r["position_value_diff"] if pd.notna(r["position_value_diff"]) else "",
            "jq_position_count": r["jq_position_count"] if pd.notna(r["jq_position_count"]) else "",
            "local_position_count": r["local_position_count"] if pd.notna(r["local_position_count"]) else "",
            "position_count_diff": r["position_count_diff"] if pd.notna(r["position_count_diff"]) else "",
            "jq_daily_return": r["jq_daily_return"] if pd.notna(r["jq_daily_return"]) else "",
            "local_daily_return": r["local_daily_return"] if pd.notna(r["local_daily_return"]) else "",
            "daily_return_diff": r["daily_return_diff"] if pd.notna(r["daily_return_diff"]) else "",
            "jq_cum_return": r["jq_cum_return"] if pd.notna(r["jq_cum_return"]) else "",
            "local_cum_return": r["local_cum_return"] if pd.notna(r["local_cum_return"]) else "",
            "cum_return_diff": r["cum_return_diff"] if pd.notna(r["cum_return_diff"]) else "",
            "match_status": r["match_status"],
            "diff_reason": r["diff_reason"],
        })

    # Stats
    stats = _compute_equity_stats(merged, jq_start_asset, local_start_asset)
    return recon_rows, stats


def _compute_equity_stats(merged, jq_start, local_start):
    """Compute equity reconciliation statistics."""
    valid = merged.dropna(subset=["jq_total_asset", "local_total_asset"])
    if valid.empty:
        return {"period_start": "", "period_end": "", "error": "no overlapping dates"}

    stats = {
        "period_start": str(valid["date"].iloc[0]),
        "period_end": str(valid["date"].iloc[-1]),
        "jq_start_asset": float(valid["jq_total_asset"].iloc[0]),
        "local_start_asset": float(valid["local_total_asset"].iloc[0]),
        "jq_end_asset": float(valid["jq_total_asset"].iloc[-1]),
        "local_end_asset": float(valid["local_total_asset"].iloc[-1]),
        "jq_total_return": float(valid["jq_total_asset"].iloc[-1] / valid["jq_total_asset"].iloc[0] - 1),
        "local_total_return": float(valid["local_total_asset"].iloc[-1] / valid["local_total_asset"].iloc[0] - 1),
        "return_diff": float(valid["jq_total_asset"].iloc[-1] / valid["jq_total_asset"].iloc[0] - 1
                             - (valid["local_total_asset"].iloc[-1] / valid["local_total_asset"].iloc[0] - 1)),
    }

    # Max drawdown
    def _max_dd(s):
        s = s.dropna()
        if s.empty:
            return 0
        peak = s.cummax()
        dd = (s - peak) / peak
        return float(dd.min())
    stats["jq_max_drawdown"] = _max_dd(valid["jq_total_asset"])
    stats["local_max_drawdown"] = _max_dd(valid["local_total_asset"])
    stats["max_drawdown_diff"] = stats["jq_max_drawdown"] - stats["local_max_drawdown"]

    # Daily return correlation
    jq_ret = valid["jq_total_asset"].pct_change().dropna()
    loc_ret = valid["local_total_asset"].pct_change().dropna()
    if len(jq_ret) > 1 and len(loc_ret) > 1:
        # Align
        common = pd.concat([jq_ret, loc_ret], axis=1, join="inner").dropna()
        if len(common) > 1:
            stats["jq_daily_return_corr"] = float(common.iloc[:, 0].corr(common.iloc[:, 1]))
        else:
            stats["jq_daily_return_corr"] = 0.0
    else:
        stats["jq_daily_return_corr"] = 0.0

    # Asset diff stats
    diffs = valid["asset_diff"].dropna().abs()
    stats["mean_abs_asset_diff"] = float(diffs.mean()) if not diffs.empty else 0
    stats["max_abs_asset_diff"] = float(diffs.max()) if not diffs.empty else 0

    # First equity divergence
    first_div_date = ""
    first_div_reason = ""
    for _, r in valid.iterrows():
        if abs(r["asset_diff"]) > 1.0:
            first_div_date = str(r["date"])
            first_div_reason = "asset_diff > 1.0"
            break
    stats["first_equity_divergence_date"] = first_div_date
    stats["first_equity_divergence_reason"] = first_div_reason

    return stats


EQUITY_RECON_FIELDS = [
    "date", "jq_total_asset", "local_total_asset", "asset_diff", "asset_diff_pct",
    "jq_cash", "local_cash", "cash_diff",
    "jq_position_value", "local_position_value", "position_value_diff",
    "jq_position_count", "local_position_count", "position_count_diff",
    "jq_daily_return", "local_daily_return", "daily_return_diff",
    "jq_cum_return", "local_cum_return", "cum_return_diff",
    "match_status", "diff_reason",
]


def write_equity_recon_csv(rows, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EQUITY_RECON_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in EQUITY_RECON_FIELDS})
    print(f"Wrote: {out_path}  ({len(rows)} rows)")


def write_equity_recon_md(stats, out_path, period_label, jq_path, local_path, evidence_level, coverage_note):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# TASK-006G-R1 Equity Reconciliation: {period_label}\n\n")
        f.write(f"## Inputs\n\n")
        f.write(f"- JQ: `{jq_path}`\n")
        f.write(f"- Local: `{local_path}`\n\n")
        f.write(f"## Evidence Level: {evidence_level}\n\n")
        f.write(f"## Coverage Note\n\n{coverage_note}\n\n")
        f.write(f"## Statistics\n\n")
        f.write("| Metric | Value |\n|--------|-------|\n")
        for k, v in stats.items():
            f.write(f"| {k} | {v} |\n")
    print(f"Wrote: {out_path}")


def main():
    print("=" * 70)
    print("TASK-006G-R1 Stage 5/6: Equity Reconciliation")
    print("=" * 70)

    # ---- 2025 (H1 only for equity) ----
    print("\n[1/2] 2025 equity reconciliation (H1 only)...")
    jq_path = OUTPUT_DIR / "JQ_2025_EQUITY_NORMALIZED.csv"
    local_path = OUTPUT_DIR.parent / "runs" / "r1_2025_research" / "equity.csv"
    if not jq_path.exists():
        print(f"  SKIP: {jq_path} not found")
    elif not local_path.exists():
        print(f"  SKIP: {local_path} not found (run Stage 3 first)")
    else:
        jq_df = load_jq_equity(jq_path)
        local_df = load_local_equity(local_path)
        # Filter local to JQ's date range (H1)
        local_h1 = local_df[(local_df["date"] >= jq_df["date"].min()) &
                            (local_df["date"] <= jq_df["date"].max())].copy()
        print(f"  JQ equity: {len(jq_df)} days ({jq_df['date'].min()}~{jq_df['date'].max()})")
        print(f"  Local equity (H1): {len(local_h1)} days")
        rows, stats = reconcile_equity(jq_df, local_h1, "2025 H1")
        write_equity_recon_csv(rows, OUTPUT_DIR / "EQUITY_RECON_2025.csv")
        coverage = ("2025 JQ equity records only cover H1 (2025-01-02 ~ 2025-06-19). "
                    "Full-year A-level equity reconciliation NOT possible. "
                    "This recon is H1 only; full-year equity evidence level is C.")
        write_equity_recon_md(stats, OUTPUT_DIR.parent / "EQUITY_RECON_2025.md",
                              "2025 H1", jq_path, local_path, "B", coverage)
        for k, v in stats.items():
            print(f"  {k}: {v}")

    # ---- 2026 fragment ----
    print("\n[2/2] 2026-05~06 fragment equity reconciliation...")
    jq_path = OUTPUT_DIR / "JQ_2026_FRAGMENT_EQUITY_NORMALIZED.csv"
    local_path = OUTPUT_DIR.parent / "runs" / "r1_2026m05_research" / "equity.csv"
    if not jq_path.exists():
        print(f"  SKIP: {jq_path} not found")
    elif not local_path.exists():
        print(f"  SKIP: {local_path} not found (run Stage 3 first)")
    else:
        jq_df = load_jq_equity(jq_path)
        local_df = load_local_equity(local_path)
        # Filter local to JQ's date range
        local_frag = local_df[(local_df["date"] >= jq_df["date"].min()) &
                              (local_df["date"] <= jq_df["date"].max())].copy()
        print(f"  JQ equity: {len(jq_df)} days ({jq_df['date'].min()}~{jq_df['date'].max()})")
        print(f"  Local equity (fragment): {len(local_frag)} days")
        rows, stats = reconcile_equity(jq_df, local_frag, "2026-05~06 fragment")
        write_equity_recon_csv(rows, OUTPUT_DIR / "EQUITY_RECON_2026_FRAGMENT.csv")
        coverage = ("2026 fragment JQ equity covers 2026-05-06 ~ 2026-06-24. "
                    "Both JQ and local start from 1M cash / empty portfolio on 2026-05-06.")
        write_equity_recon_md(stats, OUTPUT_DIR.parent / "EQUITY_RECON_2026_FRAGMENT.md",
                              "2026-05~06 fragment", jq_path, local_path, "A", coverage)
        for k, v in stats.items():
            print(f"  {k}: {v}")

    print("\n=== Equity Reconciliation Complete ===")


if __name__ == "__main__":
    main()
