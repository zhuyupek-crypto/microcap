#!/usr/bin/env python3
"""TASK-006C: Cost sensitivity post-processor.

Reads closed_trades.csv and trades.csv from a run directory and recomputes
the closed-trade metrics under four cost scenarios:

    gross      : no cost (baseline from performance_report.json)
    cost_10bp  : 0.10% single-side cost
    cost_20bp  : 0.20% single-side cost
    cost_30bp  : 0.30% single-side cost

Cost is applied as a fraction of trade value on BOTH buy and sell legs
(i.e. round-trip cost = 2 * cost_rate * notional). This is a post-processing
approximation: we do NOT re-run the backtest, do NOT change the engine, and
do NOT change which trades were filled. We only recompute P&L assuming the
same fills happened but with a per-side cost deducted from each leg.

Outputs:
    runs/<tag>/cost_sensitivity.json
    runs/<tag>/cost_sensitivity.csv  (one row per cost scenario)

Aggregate:
    runs/TASK_006C_COST_SENSITIVITY.csv  (one row per (tag, scenario))
    runs/TASK_006C_COST_SENSITIVITY.md
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any

import pandas as pd

COST_SCENARIOS = [
    ("gross", 0.0),
    ("cost_10bp", 0.001),
    ("cost_20bp", 0.002),
    ("cost_30bp", 0.003),
]

TRADING_DAYS_PER_YEAR = 252


def _load_closed_trades(run_dir: Path) -> pd.DataFrame:
    p = run_dir / "closed_trades.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
    except Exception:
        return pd.DataFrame()
    return df


def _load_equity(run_dir: Path) -> pd.DataFrame:
    p = run_dir / "equity.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["value"]).reset_index(drop=True)
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


def _compute_metrics_for_scenario(
    closed: pd.DataFrame, equity: pd.DataFrame, initial_cash: float, cost_rate: float
) -> dict:
    """Compute closed-trade metrics under a given single-side cost rate.

    For each closed trade:
        net_pnl = gross_pnl - cost_rate * (buy_notional + sell_notional)
        net_return = net_pnl / buy_notional
    where buy_notional = quantity * buy_price, sell_notional = quantity * sell_price.
    """
    if closed.empty:
        return {
            "number_of_closed_trades": 0,
            "win_rate": None,
            "average_return": None,
            "median_return": None,
            "average_win": None,
            "average_loss": None,
            "profit_loss_ratio": None,
            "expectancy_per_trade": None,
            "average_holding_days": None,
            "median_holding_days": None,
            "total_net_pnl": None,
        }

    # Compute net P&L and net return per closed trade
    buy_notional = closed["quantity"] * closed["buy_price"]
    sell_notional = closed["quantity"] * closed["sell_price"]
    round_trip_cost = cost_rate * (buy_notional + sell_notional)
    net_pnl = closed["gross_pnl"] - round_trip_cost
    net_return = net_pnl / buy_notional

    wins = net_return[net_return > 0]
    losses = net_return[net_return < 0]
    holding = closed["holding_days"]

    win_rate = len(wins) / len(closed) if len(closed) > 0 else None
    avg_return = statistics.fmean(net_return) if len(net_return) > 0 else None
    median_return = statistics.median(net_return) if len(net_return) > 0 else None
    avg_win = statistics.fmean(wins) if len(wins) > 0 else None
    avg_loss = abs(statistics.fmean(losses)) if len(losses) > 0 else None
    if avg_win is not None and avg_loss is not None and avg_loss > 0:
        pl_ratio = avg_win / avg_loss
    else:
        pl_ratio = None
    expectancy = statistics.fmean(net_return) if len(net_return) > 0 else None
    avg_holding = statistics.fmean(holding) if len(holding) > 0 else None
    median_holding = statistics.median(holding) if len(holding) > 0 else None
    total_net_pnl = float(net_pnl.sum()) if len(net_pnl) > 0 else None

    # Equity metrics under cost: subtract total round-trip cost from equity curve
    # This is an approximation: we deduct the cumulative cost from the ending value.
    # The equity curve shape (drawdown, volatility) is unchanged because costs are
    # applied as a lump-sum at the end. This is conservative for drawdown.
    eq_metrics = None
    if not equity.empty and initial_cash > 0:
        values = equity["value"].astype(float)
        ending_value_gross = float(values.iloc[-1])
        total_cost = float(round_trip_cost.sum()) if cost_rate > 0 else 0.0
        ending_value_net = ending_value_gross - total_cost
        initial_value = float(values.iloc[0])
        trading_days = len(values)

        total_return_net = ending_value_net / initial_value - 1
        cagr_net = (ending_value_net / initial_value) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1 if trading_days > 0 else None

        # Drawdown is computed on the gross curve (costs applied at end, so
        # the drawdown shape is unchanged). Report gross drawdown.
        running_peak = values.cummax()
        drawdown = values / running_peak - 1.0
        max_dd = float(drawdown.min())
        max_dd_end_idx = int(drawdown.idxmin())
        peak_value = running_peak.iloc[max_dd_end_idx]
        start_idx = max_dd_end_idx
        for i in range(max_dd_end_idx, -1, -1):
            if values.iloc[i] >= peak_value:
                start_idx = i
                break
        dates = equity["date"].tolist() if "date" in equity.columns else []
        max_dd_start = dates[start_idx] if start_idx < len(dates) else None
        max_dd_end = dates[max_dd_end_idx] if max_dd_end_idx < len(dates) else None

        daily_return = values.pct_change().fillna(0.0)
        vol = float(daily_return.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(daily_return) > 1 else None
        sharpe = (cagr_net - 0.03) / vol if vol and vol > 0 and cagr_net is not None else None

        eq_metrics = {
            "ending_value_net": ending_value_net,
            "total_return_net": float(total_return_net),
            "cagr_net": float(cagr_net) if cagr_net is not None else None,
            "max_drawdown": max_dd,  # gross drawdown (unchanged shape)
            "max_drawdown_start": max_dd_start,
            "max_drawdown_end": max_dd_end,
            "sharpe_net": float(sharpe) if sharpe is not None else None,
            "total_round_trip_cost": total_cost,
        }

    return {
        "number_of_closed_trades": int(len(closed)),
        "win_rate": float(win_rate) if win_rate is not None else None,
        "average_return": float(avg_return) if avg_return is not None else None,
        "median_return": float(median_return) if median_return is not None else None,
        "average_win": float(avg_win) if avg_win is not None else None,
        "average_loss": float(avg_loss) if avg_loss is not None else None,
        "profit_loss_ratio": float(pl_ratio) if pl_ratio is not None else None,
        "expectancy_per_trade": float(expectancy) if expectancy is not None else None,
        "average_holding_days": float(avg_holding) if avg_holding is not None else None,
        "median_holding_days": float(median_holding) if median_holding is not None else None,
        "total_net_pnl": total_net_pnl,
        "equity_metrics_net": eq_metrics,
    }


def generate_cost_sensitivity(run_dir: str | Path) -> dict:
    """Generate cost_sensitivity.json and cost_sensitivity.csv for one run."""
    run_dir = Path(run_dir)
    closed = _load_closed_trades(run_dir)
    equity = _load_equity(run_dir)
    manifest = _load_manifest(run_dir)
    initial_cash = float(manifest.get("initial_cash", 0) or 0)

    results = {}
    for name, rate in COST_SCENARIOS:
        results[name] = _compute_metrics_for_scenario(closed, equity, initial_cash, rate)

    # Tag metadata
    out = {
        "tag": manifest.get("tag", run_dir.name),
        "engine_mode": manifest.get("engine_mode"),
        "start_date": manifest.get("start_date"),
        "end_date": manifest.get("end_date"),
        "initial_cash": initial_cash if initial_cash > 0 else None,
        "scenarios": results,
        "notes": [
            "Cost is applied as a single-side rate on BOTH buy and sell legs.",
            "round_trip_cost = cost_rate * (buy_notional + sell_notional).",
            "net_pnl = gross_pnl - round_trip_cost.",
            "Equity drawdown shape is unchanged (costs applied as lump-sum at end).",
            "This is a post-processing approximation; the backtest itself is not re-run.",
        ],
    }

    (run_dir / "cost_sensitivity.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # CSV: one row per scenario
    csv_path = run_dir / "cost_sensitivity.csv"
    fields = [
        "scenario", "cost_rate", "number_of_closed_trades", "win_rate",
        "average_return", "median_return", "average_win", "average_loss",
        "profit_loss_ratio", "expectancy_per_trade", "total_net_pnl",
        "ending_value_net", "total_return_net", "cagr_net",
        "max_drawdown", "sharpe_net", "total_round_trip_cost",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for name, rate in COST_SCENARIOS:
            r = results[name]
            eq = r.get("equity_metrics_net") or {}
            w.writerow([
                name, rate, r.get("number_of_closed_trades"),
                r.get("win_rate"), r.get("average_return"),
                r.get("median_return"), r.get("average_win"),
                r.get("average_loss"), r.get("profit_loss_ratio"),
                r.get("expectancy_per_trade"), r.get("total_net_pnl"),
                eq.get("ending_value_net"), eq.get("total_return_net"),
                eq.get("cagr_net"), eq.get("max_drawdown"),
                eq.get("sharpe_net"), eq.get("total_round_trip_cost"),
            ])

    return out


# ---------------------------------------------------------------------------
# Aggregate across runs
# ---------------------------------------------------------------------------
AGG_FIELDS = [
    "tag", "scenario", "cost_rate", "number_of_closed_trades", "win_rate",
    "average_return", "median_return", "profit_loss_ratio",
    "expectancy_per_trade", "total_net_pnl",
    "ending_value_net", "total_return_net", "cagr_net",
    "max_drawdown", "sharpe_net", "total_round_trip_cost",
]


def generate_aggregate(runs_root: str | Path, tags: list[str]) -> None:
    """Write runs/TASK_006C_COST_SENSITIVITY.csv and .md."""
    runs_root = Path(runs_root)
    rows = []
    for tag in tags:
        cs_path = runs_root / tag / "cost_sensitivity.csv"
        if not cs_path.exists():
            continue
        try:
            df = pd.read_csv(cs_path)
        except Exception:
            continue
        if df.empty:
            continue
        df.insert(0, "tag", tag)
        rows.append(df)

    if not rows:
        print("No cost_sensitivity.csv files found; skipping aggregate.")
        return

    agg = pd.concat(rows, ignore_index=True)
    # Reorder columns
    cols = [c for c in AGG_FIELDS if c in agg.columns]
    agg = agg[cols]

    csv_path = runs_root / "TASK_006C_COST_SENSITIVITY.csv"
    agg.to_csv(csv_path, index=False, encoding="utf-8")

    # Markdown
    md_path = runs_root / "TASK_006C_COST_SENSITIVITY.md"
    lines = [
        "# TASK-006C Cost Sensitivity Aggregate",
        "",
        f"Scenarios: gross, cost_10bp (0.10%), cost_20bp (0.20%), cost_30bp (0.30%)",
        f"Single-side cost applied on BOTH buy and sell legs.",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "---|" * len(cols),
    ]
    for _, row in agg.iterrows():
        cells = []
        for c in cols:
            v = row.get(c)
            if pd.isna(v) or v is None:
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
    p = argparse.ArgumentParser(description="TASK-006C cost sensitivity post-processor")
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
        out = generate_cost_sensitivity(args.run_dir)
        print(f"OK: {args.run_dir} tag={out.get('tag')}")
    else:
        runs_root = Path(args.runs_root)
        for tag in args.tags:
            run_dir = runs_root / tag
            if not run_dir.exists():
                print(f"SKIP (missing): {tag}")
                continue
            out = generate_cost_sensitivity(run_dir)
            print(f"OK: {tag}")
        generate_aggregate(runs_root, args.tags)
