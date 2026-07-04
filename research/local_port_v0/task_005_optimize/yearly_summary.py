#!/usr/bin/env python3
"""TASK-006C: Yearly performance summary.

Reads closed_trades.csv and equity.csv from a run directory and computes
per-year (calendar year) performance metrics:

    - year_return             : annual return based on equity curve segment
    - year_max_drawdown       : max drawdown within the year
    - year_max_drawdown_start : start date of the year's max drawdown
    - year_max_drawdown_end   : end date of the year's max drawdown
    - year_fills              : number of fills in the year (from trades.csv)
    - year_closed_trades      : number of FIFO closed trades closed in the year
    - year_win_rate           : FIFO win rate for trades closed in the year
    - year_expectancy         : average net return per closed trade in the year
    - year_annualized_turnover: annualized gross turnover for the year

Outputs:
    runs/<tag>/yearly_summary.csv
    runs/<tag>/yearly_summary.md

Aggregate:
    runs/TASK_006C_YEARLY_SUMMARY.csv  (one row per (tag, year))
    runs/TASK_006C_YEARLY_SUMMARY.md
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

TRADING_DAYS_PER_YEAR = 252


def _load_equity(run_dir: Path) -> pd.DataFrame:
    p = run_dir / "equity.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["year"] = df["date"].dt.year
        return df.dropna(subset=["value", "date"]).reset_index(drop=True)
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
        df["year"] = df["time_dt"].dt.year
        return df.dropna(subset=["amount", "price"]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _load_closed_trades(run_dir: Path) -> pd.DataFrame:
    p = run_dir / "closed_trades.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        df["close_date_dt"] = pd.to_datetime(df["close_date"], errors="coerce")
        df["year"] = df["close_date_dt"].dt.year
        return df.dropna(subset=["gross_pnl", "gross_return"]).reset_index(drop=True)
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


def _equity_segment_metrics(eq_segment: pd.DataFrame) -> dict:
    """Compute return and drawdown for a segment of the equity curve."""
    if eq_segment.empty or len(eq_segment) < 2:
        return {
            "year_return": None,
            "year_max_drawdown": None,
            "year_max_drawdown_start": None,
            "year_max_drawdown_end": None,
            "year_trading_days": int(len(eq_segment)),
        }

    values = eq_segment["value"].astype(float).reset_index(drop=True)
    dates = eq_segment["date"].dt.strftime("%Y-%m-%d").tolist()

    # Year return: use the last value of prev year as base, or first value of this year
    # If this is the first year, base = initial value (values[0])
    # Otherwise base = last value of previous year (passed in via eq_segment including prev last day)
    # Simplification: year_return = last/first - 1 within the segment
    first_val = float(values.iloc[0])
    last_val = float(values.iloc[-1])
    year_return = last_val / first_val - 1 if first_val > 0 else None

    # Max drawdown within the segment
    running_peak = values.cummax()
    drawdown = values / running_peak - 1.0
    max_dd_end_idx = int(drawdown.idxmin())
    max_dd = float(drawdown.iloc[max_dd_end_idx])
    peak_value = running_peak.iloc[max_dd_end_idx]
    start_idx = max_dd_end_idx
    for i in range(max_dd_end_idx, -1, -1):
        if values.iloc[i] >= peak_value:
            start_idx = i
            break
    max_dd_start = dates[start_idx] if start_idx < len(dates) else None
    max_dd_end = dates[max_dd_end_idx] if max_dd_end_idx < len(dates) else None

    return {
        "year_return": float(year_return) if year_return is not None else None,
        "year_max_drawdown": max_dd,
        "year_max_drawdown_start": max_dd_start,
        "year_max_drawdown_end": max_dd_end,
        "year_trading_days": int(len(eq_segment)),
    }


def _trades_year_metrics(trades_year: pd.DataFrame, initial_cash: float) -> dict:
    if trades_year.empty:
        return {
            "year_fills": 0,
            "year_buy_fills": 0,
            "year_sell_fills": 0,
            "year_gross_turnover": 0.0,
            "year_annualized_turnover": 0.0,
        }
    buy_mask = trades_year["amount"] > 0
    sell_mask = trades_year["amount"] < 0
    buy_val = float((trades_year.loc[buy_mask, "price"] * trades_year.loc[buy_mask, "amount"]).sum())
    sell_val = float((trades_year.loc[sell_mask, "price"] * trades_year.loc[sell_mask, "amount"].abs()).sum())
    gross_val = buy_val + sell_val
    gross_turnover = gross_val / initial_cash if initial_cash > 0 else None
    trading_days = len(trades_year["time_dt"].dt.normalize().unique())
    ann_turnover = (gross_val / initial_cash) * (TRADING_DAYS_PER_YEAR / trading_days) if (initial_cash > 0 and trading_days > 0) else None
    return {
        "year_fills": int(len(trades_year)),
        "year_buy_fills": int(buy_mask.sum()),
        "year_sell_fills": int(sell_mask.sum()),
        "year_gross_turnover": gross_turnover,
        "year_annualized_turnover": ann_turnover,
    }


def _closed_year_metrics(closed_year: pd.DataFrame) -> dict:
    if closed_year.empty:
        return {
            "year_closed_trades": 0,
            "year_win_rate": None,
            "year_expectancy": None,
            "year_avg_return": None,
            "year_profit_loss_ratio": None,
            "year_avg_holding_days": None,
        }
    returns = closed_year["gross_return"]
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    win_rate = len(wins) / len(closed_year) if len(closed_year) > 0 else None
    expectancy = statistics.fmean(returns) if len(returns) > 0 else None
    avg_return = statistics.fmean(returns) if len(returns) > 0 else None
    avg_win = statistics.fmean(wins) if len(wins) > 0 else None
    avg_loss = abs(statistics.fmean(losses)) if len(losses) > 0 else None
    pl_ratio = avg_win / avg_loss if (avg_win is not None and avg_loss is not None and avg_loss > 0) else None
    avg_hold = statistics.fmean(closed_year["holding_days"]) if len(closed_year) > 0 else None
    return {
        "year_closed_trades": int(len(closed_year)),
        "year_win_rate": float(win_rate) if win_rate is not None else None,
        "year_expectancy": float(expectancy) if expectancy is not None else None,
        "year_avg_return": float(avg_return) if avg_return is not None else None,
        "year_profit_loss_ratio": float(pl_ratio) if pl_ratio is not None else None,
        "year_avg_holding_days": float(avg_hold) if avg_hold is not None else None,
    }


def generate_yearly_summary(run_dir: str | Path) -> dict:
    run_dir = Path(run_dir)
    equity = _load_equity(run_dir)
    trades = _load_trades(run_dir)
    closed = _load_closed_trades(run_dir)
    manifest = _load_manifest(run_dir)
    initial_cash = float(manifest.get("initial_cash", 0) or 0)

    if equity.empty:
        return {"tag": manifest.get("tag", run_dir.name), "years": [], "note": "equity.csv missing or empty"}

    # Determine the set of years
    years = sorted(equity["year"].dropna().unique().tolist())

    # For equity segment, include the last trading day of the previous year as the base
    # so year_return = last_day_this_year / last_day_prev_year - 1
    equity_sorted = equity.sort_values("date").reset_index(drop=True)

    rows = []
    for i, year in enumerate(years):
        year_int = int(year)
        if i == 0:
            # First year: segment from first day to last day of this year
            eq_segment = equity_sorted[equity_sorted["year"] == year].reset_index(drop=True)
        else:
            # Include last day of previous year as base
            prev_year = int(years[i - 1])
            prev_last = equity_sorted[equity_sorted["year"] == prev_year].tail(1)
            this_year_eq = equity_sorted[equity_sorted["year"] == year]
            eq_segment = pd.concat([prev_last, this_year_eq], ignore_index=True)

        eq_metrics = _equity_segment_metrics(eq_segment)

        trades_year = trades[trades["year"] == year] if not trades.empty else pd.DataFrame()
        tr_metrics = _trades_year_metrics(trades_year, initial_cash)

        closed_year = closed[closed["year"] == year] if not closed.empty else pd.DataFrame()
        cl_metrics = _closed_year_metrics(closed_year)

        row = {
            "tag": manifest.get("tag", run_dir.name),
            "year": year_int,
            **eq_metrics,
            **tr_metrics,
            **cl_metrics,
        }
        rows.append(row)

    # Write CSV
    csv_path = run_dir / "yearly_summary.csv"
    fields = [
        "tag", "year", "year_return", "year_max_drawdown",
        "year_max_drawdown_start", "year_max_drawdown_end",
        "year_trading_days", "year_fills", "year_buy_fills",
        "year_sell_fills", "year_gross_turnover",
        "year_annualized_turnover", "year_closed_trades",
        "year_win_rate", "year_expectancy", "year_avg_return",
        "year_profit_loss_ratio", "year_avg_holding_days",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})

    # Write MD
    md_path = run_dir / "yearly_summary.md"
    lines = [
        f"# Yearly Summary - {manifest.get('tag', run_dir.name)}",
        "",
        f"Initial cash: {initial_cash}",
        "",
        "| " + " | ".join(fields) + " |",
        "|" + "---|" * len(fields),
    ]
    for r in rows:
        cells = []
        for k in fields:
            v = r.get(k)
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.6f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {"tag": manifest.get("tag", run_dir.name), "years": rows}


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
AGG_FIELDS = [
    "tag", "year", "year_return", "year_max_drawdown",
    "year_max_drawdown_start", "year_max_drawdown_end",
    "year_trading_days", "year_fills", "year_closed_trades",
    "year_win_rate", "year_expectancy", "year_profit_loss_ratio",
    "year_annualized_turnover",
]


def generate_aggregate(runs_root: str | Path, tags: list[str]) -> None:
    runs_root = Path(runs_root)
    rows = []
    for tag in tags:
        p = runs_root / tag / "yearly_summary.csv"
        if not p.exists():
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if df.empty:
            continue
        rows.append(df)

    if not rows:
        print("No yearly_summary.csv files found; skipping aggregate.")
        return

    agg = pd.concat(rows, ignore_index=True)
    cols = [c for c in AGG_FIELDS if c in agg.columns]
    agg = agg[cols].sort_values(["tag", "year"]).reset_index(drop=True)

    csv_path = runs_root / "TASK_006C_YEARLY_SUMMARY.csv"
    agg.to_csv(csv_path, index=False, encoding="utf-8")

    md_path = runs_root / "TASK_006C_YEARLY_SUMMARY.md"
    lines = [
        "# TASK-006C Yearly Summary Aggregate",
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
    print(f"Yearly aggregate written: {csv_path} + {md_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="TASK-006C yearly summary")
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
        out = generate_yearly_summary(args.run_dir)
        print(f"OK: {args.run_dir} years={len(out.get('years', []))}")
    else:
        runs_root = Path(args.runs_root)
        for tag in args.tags:
            run_dir = runs_root / tag
            if not run_dir.exists():
                print(f"SKIP (missing): {tag}")
                continue
            out = generate_yearly_summary(run_dir)
            print(f"OK: {tag} years={len(out.get('years', []))}")
        generate_aggregate(runs_root, args.tags)
