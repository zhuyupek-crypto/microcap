#!/usr/bin/env python3
"""TASK-006F: jq_parity baseline vs Research comparison.

Reads performance_report.json + manifest.json from r3_*_research and
r4_*_jq_parity run directories and produces three comparison reports:

  1. TASK_006F_JQ_PARITY_SUMMARY.csv/md     - 4 jq_parity runs summary
  2. TASK_006F_RESEARCH_VS_JQ_PARITY.csv/md - per-period delta table
  3. TASK_006F_YEARLY_COMPARISON.csv/md     - full-range year-by-year

All deltas = jq_parity - research (positive delta means jq_parity higher).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
RUNS_ROOT = SCRIPT_DIR / "runs"

# (research_tag, jq_parity_tag, period_label, start, end)
PERIODS = [
    ("r3_2020_2021_research", "r4_2020_2021_jq_parity", "2020-2021", "2020-01-01", "2021-12-31"),
    ("r3_2022_2023_research", "r4_2022_2023_jq_parity", "2022-2023", "2022-01-01", "2023-12-31"),
    ("r3_2024_202605_research", "r4_2024_202605_jq_parity", "2024-2026M05", "2024-01-01", "2026-05-28"),
    ("r3_full_2020_202605_research", "r4_full_2020_202605_jq_parity", "full_2020-2026M05", "2020-01-01", "2026-05-28"),
]

JQ_TAGS = [p[1] for p in PERIODS]
FULL_RESEARCH_TAG = "r3_full_2020_202605_research"
FULL_JQ_TAG = "r4_full_2020_202605_jq_parity"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_run(run_dir: Path) -> dict[str, Any]:
    """Load performance_report.json + manifest.json for a run."""
    pr = _load_json(run_dir / "performance_report.json")
    mf = _load_json(run_dir / "manifest.json")
    if not pr and not mf:
        return {}
    # Merge: performance_report takes priority for metric fields,
    # manifest supplies engine_mode, dates, orders, rejection_reasons.
    em = pr.get("equity_metrics", {})
    tf = pr.get("trade_flow_metrics", {})
    cl = pr.get("closed_trade_metrics", {})
    eq = pr.get("execution_quality", {})
    orders = mf.get("orders", {})
    return {
        "tag": pr.get("tag", mf.get("tag", run_dir.name)),
        "engine_mode": mf.get("engine_mode", ""),
        "start_date": mf.get("start_date", pr.get("start_date", "")),
        "end_date": mf.get("end_date", pr.get("end_date", "")),
        "trading_days": em.get("trading_days", 0),
        "ending_value": em.get("ending_value", 0),
        "total_return": em.get("total_return", 0),
        "annual_return_cagr": em.get("annual_return_cagr", 0),
        "max_drawdown": em.get("max_drawdown", 0),
        "max_drawdown_start": em.get("max_drawdown_start", ""),
        "max_drawdown_end": em.get("max_drawdown_end", ""),
        "sharpe_annualized": em.get("sharpe_annualized", 0),
        "calmar": em.get("calmar", 0),
        "volatility_annualized": em.get("volatility_annualized", 0),
        "gross_turnover": tf.get("gross_turnover", 0),
        "annualized_gross_turnover": tf.get("annualized_gross_turnover", 0),
        "number_of_fills": tf.get("number_of_fills", 0),
        "number_of_buy_fills": tf.get("number_of_buy_fills", 0),
        "number_of_sell_fills": tf.get("number_of_sell_fills", 0),
        "number_of_closed_trades": cl.get("number_of_closed_trades", 0),
        "win_rate": cl.get("win_rate", 0),
        "average_return": cl.get("average_return", 0),
        "median_return": cl.get("median_return", 0),
        "profit_loss_ratio": cl.get("profit_loss_ratio", 0),
        "expectancy_per_trade": cl.get("expectancy_per_trade", 0),
        "average_holding_days": cl.get("average_holding_days", 0),
        "orders_submitted": eq.get("orders_submitted", orders.get("submitted", 0)),
        "orders_filled": eq.get("orders_filled", orders.get("filled", 0)),
        "orders_rejected": eq.get("orders_rejected", orders.get("rejected", 0)),
        "fill_rate": eq.get("fill_rate", 0),
        "rejection_reasons": eq.get("rejection_reasons", mf.get("rejection_reasons", {})),
    }


def _fmt_pct(v: float) -> str:
    return f"{v*100:.2f}%" if v is not None else ""


def _fmt_float(v: float, d: int = 4) -> str:
    return f"{v:.{d}f}" if v is not None else ""


# ---------------------------------------------------------------------------
# Report 1: JQ_PARITY_SUMMARY
# ---------------------------------------------------------------------------
SUMMARY_FIELDS = [
    "tag", "engine_mode", "start_date", "end_date", "trading_days",
    "ending_value", "total_return", "annual_return_cagr",
    "max_drawdown", "max_drawdown_start", "max_drawdown_end",
    "sharpe_annualized", "calmar", "volatility_annualized",
    "gross_turnover", "annualized_gross_turnover",
    "number_of_fills", "number_of_buy_fills", "number_of_sell_fills",
    "number_of_closed_trades", "win_rate", "average_return", "median_return",
    "profit_loss_ratio", "expectancy_per_trade", "average_holding_days",
    "orders_submitted", "orders_filled", "orders_rejected", "fill_rate",
    "rejection_reasons",
]


def generate_jq_parity_summary() -> pd.DataFrame:
    rows = []
    for tag in JQ_TAGS:
        run_dir = RUNS_ROOT / tag
        data = _load_run(run_dir)
        if not data:
            print(f"WARN: {tag} missing or empty, skipping")
            continue
        rows.append(data)
    df = pd.DataFrame(rows, columns=SUMMARY_FIELDS)
    return df


# ---------------------------------------------------------------------------
# Report 2: RESEARCH_VS_JQ_PARITY
# ---------------------------------------------------------------------------
VS_FIELDS = [
    "period", "research_tag", "jq_parity_tag",
    "research_total_return", "jq_total_return", "delta_total_return",
    "research_cagr", "jq_cagr", "delta_cagr",
    "research_max_drawdown", "jq_max_drawdown", "delta_max_drawdown",
    "research_sharpe", "jq_sharpe", "delta_sharpe",
    "research_fills", "jq_fills", "delta_fills",
    "research_closed_trades", "jq_closed_trades", "delta_closed_trades",
    "research_win_rate", "jq_win_rate", "delta_win_rate",
    "research_expectancy", "jq_expectancy", "delta_expectancy",
    "research_annualized_turnover", "jq_annualized_turnover", "delta_turnover",
    "research_fill_rate", "jq_fill_rate", "delta_fill_rate",
]


def generate_research_vs_jq() -> pd.DataFrame:
    rows = []
    for r_tag, j_tag, period, start, end in PERIODS:
        r_data = _load_run(RUNS_ROOT / r_tag)
        j_data = _load_run(RUNS_ROOT / j_tag)
        if not r_data or not j_data:
            print(f"WARN: missing data for period {period}")
            continue
        row = {
            "period": period,
            "research_tag": r_tag,
            "jq_parity_tag": j_tag,
            "research_total_return": r_data["total_return"],
            "jq_total_return": j_data["total_return"],
            "delta_total_return": j_data["total_return"] - r_data["total_return"],
            "research_cagr": r_data["annual_return_cagr"],
            "jq_cagr": j_data["annual_return_cagr"],
            "delta_cagr": j_data["annual_return_cagr"] - r_data["annual_return_cagr"],
            "research_max_drawdown": r_data["max_drawdown"],
            "jq_max_drawdown": j_data["max_drawdown"],
            "delta_max_drawdown": j_data["max_drawdown"] - r_data["max_drawdown"],
            "research_sharpe": r_data["sharpe_annualized"],
            "jq_sharpe": j_data["sharpe_annualized"],
            "delta_sharpe": j_data["sharpe_annualized"] - r_data["sharpe_annualized"],
            "research_fills": r_data["number_of_fills"],
            "jq_fills": j_data["number_of_fills"],
            "delta_fills": j_data["number_of_fills"] - r_data["number_of_fills"],
            "research_closed_trades": r_data["number_of_closed_trades"],
            "jq_closed_trades": j_data["number_of_closed_trades"],
            "delta_closed_trades": j_data["number_of_closed_trades"] - r_data["number_of_closed_trades"],
            "research_win_rate": r_data["win_rate"],
            "jq_win_rate": j_data["win_rate"],
            "delta_win_rate": j_data["win_rate"] - r_data["win_rate"],
            "research_expectancy": r_data["expectancy_per_trade"],
            "jq_expectancy": j_data["expectancy_per_trade"],
            "delta_expectancy": j_data["expectancy_per_trade"] - r_data["expectancy_per_trade"],
            "research_annualized_turnover": r_data["annualized_gross_turnover"],
            "jq_annualized_turnover": j_data["annualized_gross_turnover"],
            "delta_turnover": j_data["annualized_gross_turnover"] - r_data["annualized_gross_turnover"],
            "research_fill_rate": r_data["fill_rate"],
            "jq_fill_rate": j_data["fill_rate"],
            "delta_fill_rate": j_data["fill_rate"] - r_data["fill_rate"],
        }
        rows.append(row)
    return pd.DataFrame(rows, columns=VS_FIELDS)


# ---------------------------------------------------------------------------
# Report 3: YEARLY_COMPARISON
# ---------------------------------------------------------------------------
YEARLY_FIELDS = [
    "year",
    "research_year_return", "jq_year_return", "delta_year_return",
    "research_year_max_drawdown", "jq_year_max_drawdown", "delta_year_max_drawdown",
    "research_fills", "jq_fills", "delta_fills",
    "research_closed_trades", "jq_closed_trades", "delta_closed_trades",
    "research_win_rate", "jq_win_rate", "delta_win_rate",
    "research_expectancy", "jq_expectancy", "delta_expectancy",
    "research_annualized_turnover", "jq_annualized_turnover", "delta_turnover",
]


def generate_yearly_comparison() -> pd.DataFrame:
    r_path = RUNS_ROOT / FULL_RESEARCH_TAG / "yearly_summary.csv"
    j_path = RUNS_ROOT / FULL_JQ_TAG / "yearly_summary.csv"
    if not r_path.exists() or not j_path.exists():
        print(f"WARN: yearly_summary.csv missing for {FULL_RESEARCH_TAG} or {FULL_JQ_TAG}")
        return pd.DataFrame()
    r_df = pd.read_csv(r_path)
    j_df = pd.read_csv(j_path)
    # Merge on year
    merged = r_df.merge(j_df, on="year", suffixes=("_r", "_j"), how="outer")
    rows = []
    for _, m in merged.iterrows():
        row = {
            "year": int(m["year"]) if pd.notna(m["year"]) else 0,
            "research_year_return": m.get("year_return_r", 0),
            "jq_year_return": m.get("year_return_j", 0),
            "delta_year_return": (m.get("year_return_j", 0) or 0) - (m.get("year_return_r", 0) or 0),
            "research_year_max_drawdown": m.get("year_max_drawdown_r", 0),
            "jq_year_max_drawdown": m.get("year_max_drawdown_j", 0),
            "delta_year_max_drawdown": (m.get("year_max_drawdown_j", 0) or 0) - (m.get("year_max_drawdown_r", 0) or 0),
            "research_fills": m.get("year_fills_r", 0),
            "jq_fills": m.get("year_fills_j", 0),
            "delta_fills": (m.get("year_fills_j", 0) or 0) - (m.get("year_fills_r", 0) or 0),
            "research_closed_trades": m.get("year_closed_trades_r", 0),
            "jq_closed_trades": m.get("year_closed_trades_j", 0),
            "delta_closed_trades": (m.get("year_closed_trades_j", 0) or 0) - (m.get("year_closed_trades_r", 0) or 0),
            "research_win_rate": m.get("year_win_rate_r", 0),
            "jq_win_rate": m.get("year_win_rate_j", 0),
            "delta_win_rate": (m.get("year_win_rate_j", 0) or 0) - (m.get("year_win_rate_r", 0) or 0),
            "research_expectancy": m.get("year_expectancy_r", 0),
            "jq_expectancy": m.get("year_expectancy_j", 0),
            "delta_expectancy": (m.get("year_expectancy_j", 0) or 0) - (m.get("year_expectancy_r", 0) or 0),
            "research_annualized_turnover": m.get("year_annualized_turnover_r", 0),
            "jq_annualized_turnover": m.get("year_annualized_turnover_j", 0),
            "delta_turnover": (m.get("year_annualized_turnover_j", 0) or 0) - (m.get("year_annualized_turnover_r", 0) or 0),
        }
        rows.append(row)
    return pd.DataFrame(rows, columns=YEARLY_FIELDS)


# ---------------------------------------------------------------------------
# MD writers
# ---------------------------------------------------------------------------
def _write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8")


def _write_md(df: pd.DataFrame, path: Path, title: str) -> None:
    cols = list(df.columns)
    lines = [f"# {title}", "", "| " + " | ".join(cols) + " |",
             "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row.get(c)
            if pd.isna(v) or v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.6f}")
            elif isinstance(v, dict):
                cells.append(json.dumps(v, ensure_ascii=False)[:120])
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("TASK-006F: jq_parity baseline vs Research comparison")
    print("=" * 60)

    # 1. JQ_PARITY_SUMMARY
    print("\n[1/3] Generating JQ_PARITY_SUMMARY...")
    df1 = generate_jq_parity_summary()
    if df1.empty:
        print("ERROR: no jq_parity run data found")
        return
    _write_csv(df1, RUNS_ROOT / "TASK_006F_JQ_PARITY_SUMMARY.csv")
    _write_md(df1, RUNS_ROOT / "TASK_006F_JQ_PARITY_SUMMARY.md",
              "TASK-006F jq_parity Baseline Summary")
    print(f"  -> {len(df1)} rows, "
          f"CAGR range {df1['annual_return_cagr'].min():.4f} ~ {df1['annual_return_cagr'].max():.4f}")

    # 2. RESEARCH_VS_JQ_PARITY
    print("\n[2/3] Generating RESEARCH_VS_JQ_PARITY...")
    df2 = generate_research_vs_jq()
    if df2.empty:
        print("ERROR: no comparison data")
        return
    _write_csv(df2, RUNS_ROOT / "TASK_006F_RESEARCH_VS_JQ_PARITY.csv")
    _write_md(df2, RUNS_ROOT / "TASK_006F_RESEARCH_VS_JQ_PARITY.md",
              "TASK-006F Research vs jq_parity Comparison")
    # Print key deltas for full range
    full_row = df2[df2["period"].str.contains("full")].iloc[0] if not df2.empty else None
    if full_row is not None:
        print(f"  Full range: delta_CAGR={full_row['delta_cagr']:.4f}, "
              f"delta_fills={full_row['delta_fills']}, "
              f"delta_fill_rate={full_row['delta_fill_rate']:.4f}")

    # 3. YEARLY_COMPARISON
    print("\n[3/3] Generating YEARLY_COMPARISON...")
    df3 = generate_yearly_comparison()
    if df3.empty:
        print("WARN: yearly comparison empty (yearly_summary.csv missing)")
    else:
        _write_csv(df3, RUNS_ROOT / "TASK_006F_YEARLY_COMPARISON.csv")
        _write_md(df3, RUNS_ROOT / "TASK_006F_YEARLY_COMPARISON.md",
                  "TASK-006F Yearly Comparison (full range)")
        print(f"  -> {len(df3)} years")

    print("\nDone. Outputs in runs/TASK_006F_*.csv/md")


if __name__ == "__main__":
    main()
