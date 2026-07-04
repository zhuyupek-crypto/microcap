#!/usr/bin/env python3
"""TASK-006D: Risk control scenario evaluation.

Evaluates three classes of simple risk control on the gross daily return
series to determine whether max drawdown can be reduced to <= 20% without
destroying returns (CAGR must stay >= 25% to be "recommended").

A. Position scaling: 100% / 80% / 60% / 50%
   daily_return_scaled = daily_return * position_factor

B. Drawdown circuit breaker:
   When drawdown from peak > 10%, cut position to 50%.
   When drawdown recovers to < 5%, restore to 100%.

C. Monthly loss protection:
   When month-to-date loss > 8%, cut position to 50% for rest of month.
   Reset to 100% at start of next month.

All scenarios rebuild the equity curve from the gross daily return series
and recompute CAGR / max_drawdown / sharpe / calmar.

Outputs (per run dir):
    risk_control_scenarios.json
    risk_control_scenarios.csv

Aggregate:
    runs/TASK_006D_RISK_CONTROL.csv
    runs/TASK_006D_RISK_CONTROL.md
"""
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path

import pandas as pd

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.03


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


def _load_manifest(run_dir: Path) -> dict:
    p = run_dir / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _metrics_from_values(values: list[float], dates_str: list[str]) -> dict:
    if len(values) < 2:
        return {"cagr": None, "max_drawdown": None, "max_drawdown_start": None,
                "max_drawdown_end": None, "sharpe": None, "calmar": None,
                "final_value": None, "total_return": None}

    s = pd.Series(values)
    initial = s.iloc[0]
    ending = s.iloc[-1]
    trading_days = len(s)
    total_return = ending / initial - 1
    cagr = (ending / initial) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1 if initial > 0 else None

    daily_ret = s.pct_change().fillna(0.0)
    vol = float(daily_ret.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(daily_ret) > 1 else None
    sharpe = (cagr - RISK_FREE_RATE) / vol if (vol and vol > 0 and cagr is not None) else None

    running_peak = s.cummax()
    drawdown = s / running_peak - 1.0
    max_dd_end_idx = int(drawdown.idxmin())
    max_dd = float(drawdown.iloc[max_dd_end_idx])
    peak_val = float(running_peak.iloc[max_dd_end_idx])
    start_idx = max_dd_end_idx
    for i in range(max_dd_end_idx, -1, -1):
        if s.iloc[i] >= peak_val:
            start_idx = i
            break
    max_dd_start = dates_str[start_idx] if start_idx < len(dates_str) else None
    max_dd_end = dates_str[max_dd_end_idx] if max_dd_end_idx < len(dates_str) else None
    calmar = cagr / abs(max_dd) if (max_dd < 0 and cagr is not None) else None

    # Annualized turnover approximation: use gross turnover from manifest if available
    return {
        "cagr": float(cagr) if cagr is not None else None,
        "max_drawdown": max_dd,
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
        "sharpe": float(sharpe) if sharpe is not None else None,
        "calmar": float(calmar) if calmar is not None else None,
        "final_value": float(ending),
        "total_return": float(total_return),
        "volatility": vol,
    }


def _rebuild_equity_constant_position(daily_returns: list[float], position: float,
                                      initial_value: float) -> list[float]:
    """Rebuild equity with constant position factor applied to daily returns."""
    values = [initial_value]
    for r in daily_returns:
        values.append(values[-1] * (1.0 + r * position))
    return values


def _rebuild_equity_drawdown_breaker(daily_returns: list[float], dates: list,
                                     initial_value: float,
                                     dd_trigger: float = 0.10,
                                     dd_recover: float = 0.05,
                                     reduced_position: float = 0.50) -> list[float]:
    """Drawdown circuit breaker: cut to reduced_position when DD > trigger,
    restore to 1.0 when DD < recover."""
    values = [initial_value]
    current_position = 1.0
    peak = initial_value
    for r in daily_returns:
        new_val = values[-1] * (1.0 + r * current_position)
        values.append(new_val)
        if new_val > peak:
            peak = new_val
        dd = new_val / peak - 1.0 if peak > 0 else 0.0
        if dd < -dd_trigger:
            current_position = reduced_position
        elif dd > -dd_recover:
            current_position = 1.0
    return values


def _rebuild_equity_monthly_loss_prot(daily_returns: list[float], dates: list,
                                      initial_value: float,
                                      month_loss_trigger: float = 0.08,
                                      reduced_position: float = 0.50) -> list[float]:
    """Monthly loss protection: cut to reduced_position when MTD loss > trigger,
    restore at start of next month."""
    values = [initial_value]
    current_position = 1.0
    prev_month = None
    month_start_value = initial_value
    for i, r in enumerate(daily_returns):
        # Check month boundary
        if i < len(dates):
            month = dates[i].strftime("%Y-%m") if hasattr(dates[i], "strftime") else str(dates[i])[:7]
        else:
            month = prev_month
        if month != prev_month:
            # New month: reset position and month_start
            current_position = 1.0
            month_start_value = values[-1]
            prev_month = month
        new_val = values[-1] * (1.0 + r * current_position)
        values.append(new_val)
        # Check month-to-date loss
        mtd_return = new_val / month_start_value - 1.0 if month_start_value > 0 else 0.0
        if mtd_return < -month_loss_trigger:
            current_position = reduced_position
    return values


def generate_risk_control_scenarios(run_dir: str | Path) -> dict:
    run_dir = Path(run_dir)
    equity = _load_equity(run_dir)
    manifest = _load_manifest(run_dir)

    if equity.empty:
        return {"tag": manifest.get("tag", run_dir.name), "error": "equity.csv missing or empty"}

    initial_value = float(equity["value"].iloc[0])
    values_gross = equity["value"].astype(float).tolist()
    dates = equity["date"].tolist()
    dates_str = [d.strftime("%Y-%m-%d") for d in dates]

    # Daily returns from gross equity
    daily_returns = [0.0]  # first day has no return
    for i in range(1, len(values_gross)):
        r = values_gross[i] / values_gross[i - 1] - 1.0 if values_gross[i - 1] > 0 else 0.0
        daily_returns.append(r)

    # Gross metrics (baseline)
    gross_metrics = _metrics_from_values(values_gross, dates_str)
    gross_max_dd = gross_metrics["max_drawdown"]
    gross_cagr = gross_metrics["cagr"]

    scenarios = []

    # A. Position scaling
    for label, pos in [("pos_100", 1.0), ("pos_80", 0.8), ("pos_60", 0.6), ("pos_50", 0.5)]:
        vals = _rebuild_equity_constant_position(daily_returns, pos, initial_value)
        m = _metrics_from_values(vals, dates_str)
        scenarios.append({
            "scenario": label,
            "type": "position_scaling",
            "position_factor": pos,
            **m,
            "drawdown_reduction": (gross_max_dd - m["max_drawdown"]) if (gross_max_dd is not None and m["max_drawdown"] is not None) else None,
            "return_sacrifice": (gross_cagr - m["cagr"]) if (gross_cagr is not None and m["cagr"] is not None) else None,
            "pass_20pct_drawdown": m["max_drawdown"] is not None and m["max_drawdown"] > -0.20,
            "recommended": (m["max_drawdown"] is not None and m["max_drawdown"] > -0.20
                            and m["cagr"] is not None and m["cagr"] >= 0.25),
        })

    # B. Drawdown circuit breaker (10% trigger, 5% recover, 50% position)
    vals = _rebuild_equity_drawdown_breaker(daily_returns, dates, initial_value,
                                            dd_trigger=0.10, dd_recover=0.05,
                                            reduced_position=0.50)
    m = _metrics_from_values(vals, dates_str)
    scenarios.append({
        "scenario": "dd_breaker_10pct",
        "type": "drawdown_circuit_breaker",
        "trigger": 0.10, "recover": 0.05, "reduced_position": 0.50,
        **m,
        "drawdown_reduction": (gross_max_dd - m["max_drawdown"]) if (gross_max_dd is not None and m["max_drawdown"] is not None) else None,
        "return_sacrifice": (gross_cagr - m["cagr"]) if (gross_cagr is not None and m["cagr"] is not None) else None,
        "pass_20pct_drawdown": m["max_drawdown"] is not None and m["max_drawdown"] > -0.20,
        "recommended": (m["max_drawdown"] is not None and m["max_drawdown"] > -0.20
                        and m["cagr"] is not None and m["cagr"] >= 0.25),
    })

    # B2. Drawdown breaker with 8% trigger (more aggressive)
    vals = _rebuild_equity_drawdown_breaker(daily_returns, dates, initial_value,
                                            dd_trigger=0.08, dd_recover=0.04,
                                            reduced_position=0.50)
    m = _metrics_from_values(vals, dates_str)
    scenarios.append({
        "scenario": "dd_breaker_8pct",
        "type": "drawdown_circuit_breaker",
        "trigger": 0.08, "recover": 0.04, "reduced_position": 0.50,
        **m,
        "drawdown_reduction": (gross_max_dd - m["max_drawdown"]) if (gross_max_dd is not None and m["max_drawdown"] is not None) else None,
        "return_sacrifice": (gross_cagr - m["cagr"]) if (gross_cagr is not None and m["cagr"] is not None) else None,
        "pass_20pct_drawdown": m["max_drawdown"] is not None and m["max_drawdown"] > -0.20,
        "recommended": (m["max_drawdown"] is not None and m["max_drawdown"] > -0.20
                        and m["cagr"] is not None and m["cagr"] >= 0.25),
    })

    # C. Monthly loss protection (8% trigger, 50% position)
    vals = _rebuild_equity_monthly_loss_prot(daily_returns, dates, initial_value,
                                             month_loss_trigger=0.08,
                                             reduced_position=0.50)
    m = _metrics_from_values(vals, dates_str)
    scenarios.append({
        "scenario": "monthly_loss_8pct",
        "type": "monthly_loss_protection",
        "trigger": 0.08, "reduced_position": 0.50,
        **m,
        "drawdown_reduction": (gross_max_dd - m["max_drawdown"]) if (gross_max_dd is not None and m["max_drawdown"] is not None) else None,
        "return_sacrifice": (gross_cagr - m["cagr"]) if (gross_cagr is not None and m["cagr"] is not None) else None,
        "pass_20pct_drawdown": m["max_drawdown"] is not None and m["max_drawdown"] > -0.20,
        "recommended": (m["max_drawdown"] is not None and m["max_drawdown"] > -0.20
                        and m["cagr"] is not None and m["cagr"] >= 0.25),
    })

    # Find best recommended scenario
    recommended = [s for s in scenarios if s.get("recommended")]
    best = max(recommended, key=lambda s: s["cagr"]) if recommended else None

    out = {
        "tag": manifest.get("tag", run_dir.name),
        "gross_baseline": gross_metrics,
        "scenarios": scenarios,
        "best_recommended": best,
        "notes": [
            "All scenarios rebuild equity from gross daily returns (no engine re-run).",
            "Position scaling: daily_return * position_factor.",
            "DD breaker: cut to 50% when drawdown > trigger, restore when < recover.",
            "Monthly loss: cut to 50% when MTD loss > 8%, reset at month start.",
            "pass_20pct_drawdown = max_drawdown > -20%.",
            "recommended = pass_20pct_drawdown AND cagr >= 25%.",
        ],
    }

    (run_dir / "risk_control_scenarios.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    # CSV
    csv_path = run_dir / "risk_control_scenarios.csv"
    fields = ["scenario", "type", "cagr", "max_drawdown", "max_drawdown_start",
              "max_drawdown_end", "sharpe", "calmar", "final_value", "total_return",
              "volatility", "drawdown_reduction", "return_sacrifice",
              "pass_20pct_drawdown", "recommended"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in scenarios:
            w.writerow(s)

    return out


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
AGG_FIELDS = ["tag", "scenario", "type", "cagr", "max_drawdown",
              "max_drawdown_start", "max_drawdown_end", "sharpe", "calmar",
              "final_value", "drawdown_reduction", "return_sacrifice",
              "pass_20pct_drawdown", "recommended"]


def generate_aggregate(runs_root: str | Path, tags: list[str]) -> None:
    runs_root = Path(runs_root)
    rows = []
    for tag in tags:
        p = runs_root / tag / "risk_control_scenarios.json"
        if not p.exists():
            continue
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "error" in rep:
            continue
        for s in rep.get("scenarios", []):
            rows.append({"tag": rep.get("tag", tag), **s})

    if not rows:
        print("No risk_control_scenarios.json files found.")
        return

    csv_path = runs_root / "TASK_006D_RISK_CONTROL.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=AGG_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    md_path = runs_root / "TASK_006D_RISK_CONTROL.md"
    lines = [
        "# TASK-006D Risk Control Scenarios Aggregate",
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
            elif isinstance(v, bool):
                cells.append("TRUE" if v else "FALSE")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Risk control aggregate written: {csv_path} + {md_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="TASK-006D risk control scenarios")
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
        out = generate_risk_control_scenarios(args.run_dir)
        best = out.get("best_recommended")
        print(f"OK: {args.run_dir} best={best['scenario'] if best else 'NONE'}")
    else:
        runs_root = Path(args.runs_root)
        for tag in args.tags:
            run_dir = runs_root / tag
            if not run_dir.exists():
                print(f"SKIP (missing): {tag}")
                continue
            out = generate_risk_control_scenarios(run_dir)
            best = out.get("best_recommended")
            print(f"OK: {tag} best={best['scenario'] if best else 'NONE'}")
        generate_aggregate(runs_root, args.tags)
