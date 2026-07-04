#!/usr/bin/env python3
"""TASK-006D: Capital capacity stress test.

Estimates the maximum deployable capital under call-auction participation
constraints. Uses the ACTUAL filled trades from trades.csv and looks up the
REAL call-auction volume from HData for each stock-day to compute the
participation rate at the backtest's initial capital (1M).

Capacity scales linearly: if at 1M the max observed participation is P%,
then at capital K the participation becomes P% * (K / 1M). The capacity
ceiling for a limit L is:  K_max = 1M * L / P_max.

This does NOT re-run the strategy. It only reads:
    trades.csv  (filled trades: time, code, amount, price)
    manifest.json (initial_cash, rejection_reasons)
    HData call_auction parquet (reference: date, code, volume)

Outputs (per run dir):
    capacity_stress_test.json
    capacity_stress_test.csv   (matrix: 6 capitals x 4 limits)

Aggregate:
    runs/TASK_006D_CAPACITY.csv
    runs/TASK_006D_CAPACITY.md
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pandas as pd

# Capital scenarios (CNY)
CAPITALS = [1_000_000, 3_000_000, 5_000_000, 10_000_000, 20_000_000, 50_000_000]
CAPITAL_LABELS = ["100万", "300万", "500万", "1000万", "2000万", "5000万"]

# Auction participation limits (single-side)
LIMITS = [0.05, 0.10, 0.20, 0.30]
LIMIT_LABELS = ["5%", "10%", "20%", "30%"]

HDATA_ROOT = os.environ.get("HDATA_ROOT", r"D:\Work Space\HData")


def _load_trades(run_dir: Path) -> pd.DataFrame:
    p = run_dir / "trades.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["time_dt"] = pd.to_datetime(df["time"], errors="coerce")
        df["date_int"] = df["time_dt"].dt.strftime("%Y%m%d").astype("int64")
        df["abs_shares"] = df["amount"].abs()
        return df.dropna(subset=["amount", "price"]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _load_manifest(run_dir: Path) -> dict:
    p = run_dir / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_call_auction_volume(trades: pd.DataFrame) -> dict:
    """Build a {(date_int, code): auction_volume} lookup from HData.

    Only reads the years that appear in trades. Uses vectorized merge
    to filter to only the (date, code) pairs that appear in trades.
    """
    if trades.empty:
        return {}

    ca_dir = os.path.join(HDATA_ROOT, "data", "processed", "1d_feature", "call_auction")
    if not os.path.isdir(ca_dir):
        return {}

    years_needed = sorted(set(int(d // 10000) for d in trades["date_int"].unique()))

    # Build a DataFrame of needed (date_int, code) pairs
    needed_df = trades[["date_int", "code"]].drop_duplicates().copy()
    needed_df["date_int"] = needed_df["date_int"].astype("int64")
    needed_df["code"] = needed_df["code"].astype(str)
    needed_df["_needed"] = True

    lookup = {}
    for year in years_needed:
        pq = os.path.join(ca_dir, f"{year}.parquet")
        if not os.path.exists(pq):
            continue
        try:
            df = pd.read_parquet(pq, columns=["date", "code", "volume"])
        except Exception:
            continue
        if df.empty:
            continue
        df["date"] = df["date"].astype("int64")
        df["code"] = df["code"].astype(str)
        # Vectorized inner merge: only keep rows matching needed pairs
        merged = df.merge(needed_df, left_on=["date", "code"],
                          right_on=["date_int", "code"], how="inner")
        for _, row in merged.iterrows():
            key = (int(row["date"]), str(row["code"]))
            lookup[key] = float(row["volume"])
    return lookup


def generate_capacity_stress_test(run_dir: str | Path) -> dict:
    run_dir = Path(run_dir)
    trades = _load_trades(run_dir)
    manifest = _load_manifest(run_dir)
    initial_cash = float(manifest.get("initial_cash", 1_000_000) or 1_000_000)

    if trades.empty:
        return {"tag": manifest.get("tag", run_dir.name), "error": "trades.csv missing or empty"}

    # Build call_auction volume lookup
    ca_lookup = _load_call_auction_volume(trades)

    # Compute participation rate per trade at the backtest's initial capital
    # Separate buy and sell: only buys are constrained by order_volume_ratio
    # in the engine; sells are constrained by closeable_amount. In reality
    # both would compete for auction liquidity.
    participations_all = []
    participations_buy = []
    participations_sell = []
    matched = 0
    unmatched = 0
    for _, row in trades.iterrows():
        key = (int(row["date_int"]), str(row["code"]))
        ca_vol = ca_lookup.get(key, 0)
        if ca_vol <= 0:
            unmatched += 1
            continue
        pr = float(row["abs_shares"]) / ca_vol
        participations_all.append(pr)
        if row["amount"] > 0:
            participations_buy.append(pr)
        else:
            participations_sell.append(pr)
        matched += 1

    if not participations_all:
        return {
            "tag": manifest.get("tag", run_dir.name),
            "error": "No call_auction volume matched for any trade",
            "matched": 0, "unmatched": len(trades),
        }

    # Use BUY-only participation for capacity ceiling (engine constrains buys)
    # but report ALL and SELL for transparency
    buy_max_pr = max(participations_buy) if participations_buy else 0
    buy_p95_pr = float(pd.Series(participations_buy).quantile(0.95)) if participations_buy else 0
    buy_median_pr = float(pd.Series(participations_buy).median()) if participations_buy else 0
    sell_max_pr = max(participations_sell) if participations_sell else 0
    sell_p95_pr = float(pd.Series(participations_sell).quantile(0.95)) if participations_sell else 0

    max_pr = max(buy_max_pr, sell_max_pr)  # overall max for reporting
    p95_pr = float(pd.Series(participations_all).quantile(0.95))
    p99_pr = float(pd.Series(participations_all).quantile(0.99))
    median_pr = float(pd.Series(participations_all).median())

    # Capacity ceiling: based on BUY-only max participation (engine constrains buys)
    # Sells are reported separately for transparency.
    capacity_ceilings = {}
    for label, limit in zip(LIMIT_LABELS, LIMITS):
        k_max = initial_cash * limit / buy_max_pr if buy_max_pr > 0 else None
        capacity_ceilings[label] = k_max

    # Stress matrix: for each (capital, limit), estimate fill rate
    # Use BUY-only participations (sells are position-driven, not auction-driven)
    # Build a list of (participation, trade_value) for buy trades
    buy_pr_values = []
    for _, row in trades.iterrows():
        key = (int(row["date_int"]), str(row["code"]))
        ca_vol = ca_lookup.get(key, 0)
        if ca_vol <= 0 or row["amount"] <= 0:
            continue
        pr = float(row["abs_shares"]) / ca_vol
        tv = float(row["price"] * row["abs_shares"])
        buy_pr_values.append((pr, tv))

    total_buy_value = sum(tv for _, tv in buy_pr_values)

    matrix_rows = []
    for cap_label, cap in zip(CAPITAL_LABELS, CAPITALS):
        scale = cap / initial_cash
        for lim_label, lim in zip(LIMIT_LABELS, LIMITS):
            # Count BUY trades that would still fit
            fits = sum(1 for pr, _ in buy_pr_values if pr * scale <= lim)
            est_fill_rate = fits / len(buy_pr_values) if buy_pr_values else 0
            est_unfilled_value = sum(tv for pr, tv in buy_pr_values if pr * scale > lim)
            est_turnover_loss = est_unfilled_value / total_buy_value if total_buy_value > 0 else 0
            capacity_pass = "PASS" if est_fill_rate >= 0.95 else "FAIL"
            matrix_rows.append({
                "capital_label": cap_label,
                "capital": cap,
                "auction_participation_limit": lim_label,
                "limit_rate": lim,
                "estimated_fill_rate": round(est_fill_rate, 4),
                "estimated_unfilled_value": round(est_unfilled_value, 2),
                "estimated_turnover_loss": round(est_turnover_loss, 4),
                "capacity_pass": capacity_pass,
            })

    # Recommended capital tiers (based on BUY-only participation)
    # Conservative: 5% limit, fill_rate >= 95%
    # Neutral: 10% limit, fill_rate >= 90%
    # Aggressive: 20% limit, fill_rate >= 80%
    def _tier_cap(target_limit_label, min_fill_rate):
        for row in matrix_rows:
            if (row["auction_participation_limit"] == target_limit_label
                    and row["estimated_fill_rate"] >= min_fill_rate):
                return row["capital"]
        return CAPITALS[0]  # fallback to smallest

    conservative_cap = _tier_cap("5%", 0.95)
    neutral_cap = _tier_cap("10%", 0.90)
    aggressive_cap = _tier_cap("20%", 0.80)
    max_recommended = min(capacity_ceilings.get("5%", conservative_cap) or conservative_cap,
                          conservative_cap)

    out = {
        "tag": manifest.get("tag", run_dir.name),
        "initial_cash": initial_cash,
        "participation_stats": {
            "buy_max_participation": round(buy_max_pr, 6),
            "buy_p95_participation": round(buy_p95_pr, 6),
            "buy_median_participation": round(buy_median_pr, 6),
            "sell_max_participation": round(sell_max_pr, 6),
            "sell_p95_participation": round(sell_p95_pr, 6),
            "all_max_participation": round(max_pr, 6),
            "all_p95_participation": round(p95_pr, 6),
            "all_p99_participation": round(p99_pr, 6),
            "all_median_participation": round(median_pr, 6),
            "matched_trades": matched,
            "unmatched_trades": unmatched,
            "buy_trades": len(participations_buy),
            "sell_trades": len(participations_sell),
        },
        "capacity_ceilings": {k: round(v, 2) if v else None for k, v in capacity_ceilings.items()},
        "recommended_capital_tiers": {
            "conservative": {
                "capital": conservative_cap,
                "rule": "5% buy auction participation, fill_rate >= 95%",
            },
            "neutral": {
                "capital": neutral_cap,
                "rule": "10% buy auction participation, fill_rate >= 90%",
            },
            "aggressive": {
                "capital": aggressive_cap,
                "rule": "20% buy auction participation, fill_rate >= 80%",
            },
            "max_recommended": max_recommended,
        },
        "stress_matrix": matrix_rows,
        "notes": [
            "Capacity is based on CALL-AUCTION volume (09:25 snapshot), not full-day volume.",
            "Buy participation = abs(buy_shares) / call_auction.volume.",
            "Sell participation reported separately (sells are position-driven, not auction-constrained).",
            "Capacity ceiling uses BUY-only max participation (engine constrains buys via order_volume_ratio).",
            "At capital K, buy participation scales linearly by K/initial_cash.",
            f"{unmatched} trades had no matching call_auction record and were excluded.",
            "This is a static capacity estimate; it does NOT account for market impact "
            "or adverse selection that would occur at higher participation rates.",
        ],
    }

    (run_dir / "capacity_stress_test.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    # CSV: stress matrix
    csv_path = run_dir / "capacity_stress_test.csv"
    fields = ["capital_label", "capital", "auction_participation_limit", "limit_rate",
              "estimated_fill_rate", "estimated_unfilled_value",
              "estimated_turnover_loss", "capacity_pass"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in matrix_rows:
            w.writerow(r)

    return out


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
def generate_aggregate(runs_root: str | Path, tags: list[str]) -> None:
    runs_root = Path(runs_root)
    rows = []
    for tag in tags:
        p = runs_root / tag / "capacity_stress_test.json"
        if not p.exists():
            continue
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "error" in rep:
            continue
        stats = rep.get("participation_stats", {})
        tiers = rep.get("recommended_capital_tiers", {})
        ceilings = rep.get("capacity_ceilings", {})
        rows.append({
            "tag": rep.get("tag", tag),
            "initial_cash": rep.get("initial_cash"),
            "buy_max_participation": stats.get("buy_max_participation"),
            "buy_p95_participation": stats.get("buy_p95_participation"),
            "buy_median_participation": stats.get("buy_median_participation"),
            "sell_max_participation": stats.get("sell_max_participation"),
            "all_max_participation": stats.get("all_max_participation"),
            "matched_trades": stats.get("matched_trades"),
            "conservative_cap": tiers.get("conservative", {}).get("capital"),
            "neutral_cap": tiers.get("neutral", {}).get("capital"),
            "aggressive_cap": tiers.get("aggressive", {}).get("capital"),
            "max_recommended": tiers.get("max_recommended"),
            "ceiling_5pct": ceilings.get("5%"),
            "ceiling_10pct": ceilings.get("10%"),
            "ceiling_20pct": ceilings.get("20%"),
            "ceiling_30pct": ceilings.get("30%"),
        })

    if not rows:
        print("No capacity_stress_test.json files found.")
        return

    csv_path = runs_root / "TASK_006D_CAPACITY.csv"
    fields = list(rows[0].keys())
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})

    md_path = runs_root / "TASK_006D_CAPACITY.md"
    lines = [
        "# TASK-006D Capacity Stress Test Aggregate",
        "",
        f"Based on call-auction participation at initial capital 1M.",
        "",
        "| " + " | ".join(fields) + " |",
        "|" + "---|" * len(fields),
    ]
    for r in rows:
        cells = []
        for c in fields:
            v = r.get(c)
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.6f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Capacity aggregate written: {csv_path} + {md_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="TASK-006D capacity stress test")
    p.add_argument("--run-dir", help="Single run directory")
    p.add_argument("--runs-root", default=str(Path(__file__).parent / "runs"))
    p.add_argument("--tags", nargs="*", default=[
        "r3_2020_2021_research",
        "r3_2022_2023_research",
        "r3_2024_202605_research",
        "r3_full_2020_202605_research",
    ])
    args = p.parse_args()

    if args.run_dir:
        out = generate_capacity_stress_test(args.run_dir)
        print(f"OK: {args.run_dir} max_pr={out.get('participation_stats', {}).get('max_participation_at_initial_capital')}")
    else:
        runs_root = Path(args.runs_root)
        for tag in args.tags:
            run_dir = runs_root / tag
            if not run_dir.exists():
                print(f"SKIP (missing): {tag}")
                continue
            out = generate_capacity_stress_test(run_dir)
            if "error" in out:
                print(f"ERR: {tag} - {out['error']}")
            else:
                print(f"OK: {tag}")
        generate_aggregate(runs_root, args.tags)
