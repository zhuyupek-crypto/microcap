#!/usr/bin/env python3
"""TASK-006D: Cost-adjusted daily equity curve recomputation.

Reads equity.csv + trades.csv + manifest.json from a run directory and
rebuilds a NET-OF-COST daily equity curve under multiple single-side
cost scenarios. Drawdown, Sharpe, volatility are ALL recomputed from
the net curve (not the gross curve).

Cost model:
    For each trading day t:
        daily_trade_value = sum(abs(price * amount)) for fills on day t
        daily_cost = cost_rate * daily_trade_value   # single-side, applied
                                                     # to BOTH buy and sell
        cumulative_cost[t] = cumulative_cost[t-1] + daily_cost
        net_equity[t] = gross_equity[t] - cumulative_cost[t]

This is a daily-granularity approximation: costs are deducted on the day
they occur (not spread intraday), so intraday drawdown shape is preserved
per day but the cumulative drag compounds day by day. This is MORE
realistic than the TASK-006C lump-sum-at-end approach.

Cost scenarios:
    gross (0bp), 10bp, 20bp, 30bp, 50bp

Outputs (per run dir):
    cost_adjusted_equity_10bp.csv   (date, gross_value, net_value, cum_cost)
    cost_adjusted_equity_20bp.csv
    cost_adjusted_equity_30bp.csv
    cost_adjusted_equity_50bp.csv
    cost_adjusted_performance.json  (metrics for all 5 scenarios)

Aggregate:
    runs/TASK_006D_COST_EQUITY.csv  (one row per (tag, scenario))
    runs/TASK_006D_COST_EQUITY.md
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics
from pathlib import Path

import pandas as pd

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.03

SCENARIOS = [
    ("gross", 0.0),
    ("cost_10bp", 0.001),
    ("cost_20bp", 0.002),
    ("cost_30bp", 0.003),
    ("cost_50bp", 0.005),
]


def _load_equity(run_dir: Path) -> pd.DataFrame:
    p = run_dir / "equity.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df.dropna(subset=["value", "date"]).sort_values("date").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _load_trades(run_dir: Path) -> pd.DataFrame:
    p = run_dir / "trades.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["time_dt"] = pd.to_datetime(df["time"], errors="coerce")
        df["date"] = df["time_dt"].dt.normalize()
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


def _compute_metrics(values: pd.Series, dates: list, initial_value: float) -> dict:
    """Compute CAGR / max_dd / sharpe / calmar from a value series."""
    if len(values) < 2:
        return {
            "initial_value": float(values.iloc[0]) if len(values) > 0 else None,
            "ending_value": float(values.iloc[-1]) if len(values) > 0 else None,
            "total_return": None, "cagr": None,
            "max_drawdown": None, "max_drawdown_start": None, "max_drawdown_end": None,
            "volatility": None, "sharpe": None, "calmar": None, "trading_days": len(values),
        }

    initial = float(values.iloc[0])
    ending = float(values.iloc[-1])
    trading_days = len(values)
    total_return = ending / initial - 1
    cagr = (ending / initial) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1 if initial > 0 else None

    daily_ret = values.pct_change().fillna(0.0)
    vol = float(daily_ret.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(daily_ret) > 1 else None
    sharpe = (cagr - RISK_FREE_RATE) / vol if (vol and vol > 0 and cagr is not None) else None

    running_peak = values.cummax()
    drawdown = values / running_peak - 1.0
    max_dd_end_idx = int(drawdown.idxmin())
    max_dd = float(drawdown.iloc[max_dd_end_idx])
    peak_val = running_peak.iloc[max_dd_end_idx]
    start_idx = max_dd_end_idx
    for i in range(max_dd_end_idx, -1, -1):
        if values.iloc[i] >= peak_val:
            start_idx = i
            break
    max_dd_start = dates[start_idx] if start_idx < len(dates) else None
    max_dd_end = dates[max_dd_end_idx] if max_dd_end_idx < len(dates) else None
    calmar = cagr / abs(max_dd) if (max_dd < 0 and cagr is not None) else None

    return {
        "initial_value": initial,
        "ending_value": ending,
        "total_return": float(total_return),
        "cagr": float(cagr) if cagr is not None else None,
        "max_drawdown": max_dd,
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
        "volatility": vol,
        "sharpe": float(sharpe) if sharpe is not None else None,
        "calmar": float(calmar) if calmar is not None else None,
        "trading_days": trading_days,
    }


def generate_cost_adjusted_equity(run_dir: str | Path) -> dict:
    run_dir = Path(run_dir)
    equity = _load_equity(run_dir)
    trades = _load_trades(run_dir)
    manifest = _load_manifest(run_dir)

    if equity.empty:
        return {"tag": manifest.get("tag", run_dir.name), "error": "equity.csv missing or empty"}

    # Aggregate trade value per day (matching equity dates)
    if not trades.empty:
        daily_trade_val = trades.groupby("date").apply(
            lambda g: float((g["price"] * g["amount"].abs()).sum())
        ).rename("trade_value")
        # Merge onto equity by date
        equity["date_norm"] = equity["date"].dt.normalize()
        equity = equity.merge(daily_trade_val, left_on="date_norm", right_index=True, how="left")
        equity["trade_value"] = equity["trade_value"].fillna(0.0)
    else:
        equity["trade_value"] = 0.0

    dates_str = equity["date"].dt.strftime("%Y-%m-%d").tolist()
    gross_values = equity["value"].astype(float).reset_index(drop=True)
    trade_values = equity["trade_value"].astype(float).reset_index(drop=True)

    results = {}
    for name, rate in SCENARIOS:
        # Build cumulative cost and net equity
        cum_cost = (trade_values * rate).cumsum()
        net_values = gross_values - cum_cost

        metrics = _compute_metrics(net_values, dates_str, float(gross_values.iloc[0]))
        metrics["cost_rate"] = rate
        metrics["total_round_trip_cost"] = float(cum_cost.iloc[-1]) if len(cum_cost) > 0 else 0.0
        results[name] = metrics

        # Write per-scenario equity CSV (skip gross, it's the original)
        if rate > 0:
            bp_label = name.replace("cost_", "")
            out_df = pd.DataFrame({
                "date": dates_str,
                "gross_value": gross_values.values,
                "net_value": net_values.values,
                "cum_cost": cum_cost.values,
                "daily_trade_value": trade_values.values,
            })
            out_df.to_csv(run_dir / f"cost_adjusted_equity_{bp_label}.csv", index=False, encoding="utf-8")

    # Write performance JSON
    out = {
        "tag": manifest.get("tag", run_dir.name),
        "engine_mode": manifest.get("engine_mode"),
        "start_date": manifest.get("start_date"),
        "end_date": manifest.get("end_date"),
        "scenarios": results,
        "notes": [
            "Cost is deducted DAILY (on the day the trade occurs), not lump-sum at end.",
            "single-side cost_rate applied to BOTH buy and sell => round_trip = 2*rate*notional.",
            "daily_cost = cost_rate * sum(abs(price*amount)) for fills that day.",
            "net_equity[t] = gross_equity[t] - cumulative_cost[t].",
            "Drawdown, volatility, Sharpe are ALL recomputed from the net curve.",
        ],
    }
    (run_dir / "cost_adjusted_performance.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    return out


# ---------------------------------------------------------------------------
# Yearly breakdown
# ---------------------------------------------------------------------------
def generate_yearly_cost_breakdown(run_dir: str | Path) -> dict:
    """Per-year metrics under each cost scenario."""
    run_dir = Path(run_dir)
    equity = _load_equity(run_dir)
    trades = _load_trades(run_dir)
    manifest = _load_manifest(run_dir)

    if equity.empty:
        return {"tag": manifest.get("tag", run_dir.name), "years": []}

    if not trades.empty:
        daily_trade_val = trades.groupby("date").apply(
            lambda g: float((g["price"] * g["amount"].abs()).sum())
        ).rename("trade_value")
        equity["date_norm"] = equity["date"].dt.normalize()
        equity = equity.merge(daily_trade_val, left_on="date_norm", right_index=True, how="left")
        equity["trade_value"] = equity["trade_value"].fillna(0.0)
    else:
        equity["trade_value"] = 0.0

    equity["year"] = equity["date"].dt.year
    years = sorted(equity["year"].dropna().unique().tolist())

    yearly_rows = []
    for i, year in enumerate(years):
        year_int = int(year)
        if i == 0:
            seg = equity[equity["year"] == year].reset_index(drop=True)
        else:
            prev_year = int(years[i - 1])
            prev_last = equity[equity["year"] == prev_year].tail(1)
            this_year = equity[equity["year"] == year]
            seg = pd.concat([prev_last, this_year], ignore_index=True)

        dates_str = seg["date"].dt.strftime("%Y-%m-%d").tolist()
        gross_vals = seg["value"].astype(float).reset_index(drop=True)
        trade_vals = seg["trade_value"].astype(float).reset_index(drop=True)

        row = {"year": year_int}
        for name, rate in SCENARIOS:
            cum_cost = (trade_vals * rate).cumsum()
            net_vals = gross_vals - cum_cost
            m = _compute_metrics(net_vals, dates_str, float(gross_vals.iloc[0]))
            row[f"{name}_cagr"] = m["cagr"]
            row[f"{name}_max_dd"] = m["max_drawdown"]
            row[f"{name}_sharpe"] = m["sharpe"]
        yearly_rows.append(row)

    # Write CSV
    csv_path = run_dir / "cost_adjusted_yearly.csv"
    fields = ["year"] + [f"{n}_cagr" for n, _ in SCENARIOS] + \
             [f"{n}_max_dd" for n, _ in SCENARIOS] + [f"{n}_sharpe" for n, _ in SCENARIOS]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in yearly_rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})

    return {"tag": manifest.get("tag", run_dir.name), "years": yearly_rows}


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
AGG_FIELDS = [
    "tag", "scenario", "cost_rate", "cagr", "max_drawdown",
    "max_drawdown_start", "max_drawdown_end", "volatility", "sharpe",
    "calmar", "total_return", "ending_value", "total_round_trip_cost",
]


def generate_aggregate(runs_root: str | Path, tags: list[str]) -> None:
    runs_root = Path(runs_root)
    rows = []
    for tag in tags:
        p = runs_root / tag / "cost_adjusted_performance.json"
        if not p.exists():
            continue
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        scenarios = rep.get("scenarios", {})
        for name, m in scenarios.items():
            rows.append({
                "tag": rep.get("tag", tag),
                "scenario": name,
                "cost_rate": m.get("cost_rate"),
                "cagr": m.get("cagr"),
                "max_drawdown": m.get("max_drawdown"),
                "max_drawdown_start": m.get("max_drawdown_start"),
                "max_drawdown_end": m.get("max_drawdown_end"),
                "volatility": m.get("volatility"),
                "sharpe": m.get("sharpe"),
                "calmar": m.get("calmar"),
                "total_return": m.get("total_return"),
                "ending_value": m.get("ending_value"),
                "total_round_trip_cost": m.get("total_round_trip_cost"),
            })

    if not rows:
        print("No cost_adjusted_performance.json files found.")
        return

    csv_path = runs_root / "TASK_006D_COST_EQUITY.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=AGG_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in AGG_FIELDS})

    md_path = runs_root / "TASK_006D_COST_EQUITY.md"
    lines = [
        "# TASK-006D Cost-Adjusted Equity Aggregate",
        "",
        f"Scenarios: gross, cost_10bp, cost_20bp, cost_30bp, cost_50bp",
        f"Single-side cost applied on BOTH buy and sell legs, deducted DAILY.",
        "",
        "| " + " | ".join(AGG_FIELDS) + " |",
        "|" + "---|" * len(AGG_FIELDS),
    ]
    for r in rows:
        cells = []
        for c in AGG_FIELDS:
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
    print(f"Aggregate written: {csv_path} + {md_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="TASK-006D cost-adjusted equity curve")
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
        out = generate_cost_adjusted_equity(args.run_dir)
        generate_yearly_cost_breakdown(args.run_dir)
        print(f"OK: {args.run_dir}")
    else:
        runs_root = Path(args.runs_root)
        for tag in args.tags:
            run_dir = runs_root / tag
            if not run_dir.exists():
                print(f"SKIP (missing): {tag}")
                continue
            generate_cost_adjusted_equity(run_dir)
            generate_yearly_cost_breakdown(run_dir)
            print(f"OK: {tag}")
        generate_aggregate(runs_root, args.tags)
