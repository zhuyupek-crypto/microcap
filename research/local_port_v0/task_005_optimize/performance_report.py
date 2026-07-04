#!/usr/bin/env python3
"""TASK-006B: Performance report generator (pure stats logic).

This module computes all performance/metrics from the three run artifacts:
    equity.csv     - daily mark-to-market portfolio value (date, value)
    trades.csv     - filled trade blotter (time, code, amount, price, ...)
    manifest.json  - run metadata (initial_cash, orders, ending_positions, ...)

It NEVER re-runs the strategy, NEVER accesses market data, and NEVER imports
the local_quant engine. All numbers are derived strictly from those three
files. If a metric cannot be computed from the available data, it is set to
``null`` and a note is added explaining why.

Public API
----------
generate_report(run_dir) -> dict
    Generate performance_report.json, summary.md, closed_trades.csv in
    ``run_dir``. Returns the report dict.

generate_summary(runs_root, tags) -> None
    Write runs/TASK_006B_SUMMARY.md and runs/TASK_006B_SUMMARY.csv
    aggregating one row per run tag.
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

RISK_FREE_RATE = 0.03
TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _load_equity(run_dir: Path) -> Optional[pd.DataFrame]:
    p = run_dir / "equity.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    if df.empty or "value" not in df.columns:
        return None
    # date column may be string; keep as-is for display, parse for math
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).reset_index(drop=True)
    return df


def _load_trades(run_dir: Path) -> Optional[pd.DataFrame]:
    p = run_dir / "trades.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    if df.empty:
        return df
    required = {"time", "code", "amount", "price"}
    if not required.issubset(df.columns):
        return None
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["amount", "price"]).reset_index(drop=True)
    # Parse time -> date string and datetime
    df["time_dt"] = pd.to_datetime(df["time"], errors="coerce")
    df["date"] = df["time_dt"].dt.strftime("%Y-%m-%d")
    return df


def _load_manifest(run_dir: Path) -> dict:
    p = run_dir / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Equity metrics
# ---------------------------------------------------------------------------
def _equity_metrics(equity: Optional[pd.DataFrame]) -> dict:
    """Compute metrics from the daily equity curve.

    All formulas follow the TASK-006B spec verbatim.
    """
    if equity is None or equity.empty:
        return {
            "initial_value": None,
            "ending_value": None,
            "total_return": None,
            "annual_return_cagr": None,
            "max_drawdown": None,
            "max_drawdown_start": None,
            "max_drawdown_end": None,
            "volatility_annualized": None,
            "sharpe_annualized": None,
            "calmar": None,
            "trading_days": 0,
        }

    values = equity["value"].astype(float).reset_index(drop=True)
    dates = equity["date"].tolist()
    initial_value = float(values.iloc[0])
    ending_value = float(values.iloc[-1])
    trading_days = int(len(values))

    total_return = ending_value / initial_value - 1

    # CAGR
    if trading_days > 0 and initial_value > 0:
        annual_return_cagr = (ending_value / initial_value) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1
    else:
        annual_return_cagr = None

    # Daily returns
    daily_return = values.pct_change().fillna(0.0)

    # Volatility (annualized)
    if len(daily_return) > 1:
        vol = float(daily_return.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        vol = None

    # Sharpe
    if vol and vol > 0 and annual_return_cagr is not None:
        sharpe = (annual_return_cagr - RISK_FREE_RATE) / vol
    else:
        sharpe = None

    # Max drawdown with start/end dates
    running_peak = values.cummax()
    drawdown = values / running_peak - 1.0
    max_dd_end_idx = int(drawdown.idxmin())  # idx of most negative drawdown
    max_dd = float(drawdown.iloc[max_dd_end_idx])
    # Find the latest peak date on or before max_dd_end_idx
    peak_value = running_peak.iloc[max_dd_end_idx]
    # Search backwards from max_dd_end_idx for the first index where value == peak_value
    start_idx = max_dd_end_idx
    for i in range(max_dd_end_idx, -1, -1):
        if values.iloc[i] >= peak_value:
            start_idx = i
            break
    max_dd_start = dates[start_idx] if start_idx < len(dates) else None
    max_dd_end = dates[max_dd_end_idx] if max_dd_end_idx < len(dates) else None

    # Calmar
    if max_dd < 0 and annual_return_cagr is not None:
        calmar = annual_return_cagr / abs(max_dd)
    else:
        calmar = None

    return {
        "initial_value": initial_value,
        "ending_value": ending_value,
        "total_return": float(total_return),
        "annual_return_cagr": float(annual_return_cagr) if annual_return_cagr is not None else None,
        "max_drawdown": float(max_dd),
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
        "volatility_annualized": vol,
        "sharpe_annualized": float(sharpe) if sharpe is not None else None,
        "calmar": float(calmar) if calmar is not None else None,
        "trading_days": trading_days,
    }


# ---------------------------------------------------------------------------
# Trade flow metrics
# ---------------------------------------------------------------------------
def _trade_flow_metrics(trades: Optional[pd.DataFrame], initial_cash: float) -> dict:
    if trades is None or trades.empty:
        return {
            "buy_turnover": 0.0,
            "sell_turnover": 0.0,
            "gross_turnover": 0.0,
            "annualized_gross_turnover": 0.0,
            "number_of_fills": 0,
            "number_of_buy_fills": 0,
            "number_of_sell_fills": 0,
        }

    buy_mask = trades["amount"] > 0
    sell_mask = trades["amount"] < 0
    buy_value = float((trades.loc[buy_mask, "price"] * trades.loc[buy_mask, "amount"]).sum())
    sell_value = float((trades.loc[sell_mask, "price"] * trades.loc[sell_mask, "amount"].abs()).sum())
    gross_value = buy_value + sell_value

    buy_turnover = buy_value / initial_cash if initial_cash > 0 else None
    sell_turnover = sell_value / initial_cash if initial_cash > 0 else None
    gross_turnover = gross_value / initial_cash if initial_cash > 0 else None

    # Annualization requires trading_days; caller patches this after equity metrics
    return {
        "buy_turnover": buy_turnover,
        "sell_turnover": sell_turnover,
        "gross_turnover": gross_turnover,
        "annualized_gross_turnover": None,  # patched by caller
        "number_of_fills": int(len(trades)),
        "number_of_buy_fills": int(buy_mask.sum()),
        "number_of_sell_fills": int(sell_mask.sum()),
        "_gross_value": gross_value,  # internal, used by caller for annualization
    }


# ---------------------------------------------------------------------------
# Closed trades via FIFO
# ---------------------------------------------------------------------------
@dataclass
class _BuyLot:
    date: str          # YYYY-MM-DD
    dt: pd.Timestamp
    remaining: int     # shares still unmatched
    price: float


@dataclass
class ClosedTrade:
    code: str
    open_date: str
    close_date: str
    quantity: int
    buy_price: float
    sell_price: float
    gross_pnl: float
    gross_return: float
    holding_days: int


def _build_closed_trades(trades: Optional[pd.DataFrame]) -> list[ClosedTrade]:
    """Match sells against buys in FIFO order, splitting sells as needed.

    A single sell that exhausts multiple buy lots produces multiple
    ClosedTrade rows (one per consumed lot). A sell that partially consumes
    a lot consumes only the needed quantity and leaves the rest in queue.
    """
    if trades is None or trades.empty:
        return []

    # Sort by trade time (use trade_id as tiebreaker if present)
    sort_cols = ["time_dt"]
    if "trade_id" in trades.columns:
        sort_cols.append("trade_id")
    trades_sorted = trades.sort_values(by=sort_cols).reset_index(drop=True)

    queues: dict[str, list[_BuyLot]] = {}
    closed: list[ClosedTrade] = []

    for _, row in trades_sorted.iterrows():
        code = str(row["code"])
        amount = int(row["amount"])
        price = float(row["price"])
        trade_date = row.get("date")
        trade_dt = row.get("time_dt")

        if amount == 0:
            continue

        if amount > 0:
            # Buy: enqueue a lot
            queues.setdefault(code, []).append(
                _BuyLot(date=trade_date, dt=trade_dt, remaining=amount, price=price)
            )
            continue

        # Sell: dequeue FIFO, possibly splitting across lots
        sell_remaining = -amount  # positive shares to close
        q = queues.setdefault(code, [])
        while sell_remaining > 0 and q:
            lot = q[0]
            matched = min(sell_remaining, lot.remaining)
            lot.remaining -= matched
            sell_remaining -= matched

            gross_pnl = (price - lot.price) * matched
            gross_return = (price / lot.price - 1.0) if lot.price > 0 else 0.0
            if trade_dt is not None and lot.dt is not None and not pd.isna(trade_dt) and not pd.isna(lot.dt):
                holding_days = int((trade_dt.normalize() - lot.dt.normalize()).days)
            else:
                holding_days = 0

            closed.append(ClosedTrade(
                code=code,
                open_date=lot.date,
                close_date=trade_date,
                quantity=matched,
                buy_price=lot.price,
                sell_price=price,
                gross_pnl=float(gross_pnl),
                gross_return=float(gross_return),
                holding_days=holding_days,
            ))

            if lot.remaining == 0:
                q.pop(0)

        # Any leftover sell with no matching buy lot is ignored (naked short
        # should not happen in this strategy; we record it via notes if needed).

    return closed


def _closed_trade_metrics(closed: list[ClosedTrade]) -> dict:
    if not closed:
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
        }

    returns = [c.gross_return for c in closed]
    pnls = [c.gross_pnl for c in closed]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    holding = [c.holding_days for c in closed]

    win_rate = len(wins) / len(closed)
    avg_return = statistics.fmean(returns)
    median_return = statistics.median(returns)
    avg_win = statistics.fmean(wins) if wins else None
    avg_loss = abs(statistics.fmean(losses)) if losses else None
    if avg_win is not None and avg_loss is not None and avg_loss > 0:
        pl_ratio = avg_win / avg_loss
    else:
        pl_ratio = None
    expectancy = statistics.fmean(returns)
    avg_holding = statistics.fmean(holding)
    median_holding = statistics.median(holding)

    return {
        "number_of_closed_trades": len(closed),
        "win_rate": float(win_rate),
        "average_return": float(avg_return),
        "median_return": float(median_return),
        "average_win": float(avg_win) if avg_win is not None else None,
        "average_loss": float(avg_loss) if avg_loss is not None else None,
        "profit_loss_ratio": float(pl_ratio) if pl_ratio is not None else None,
        "expectancy_per_trade": float(expectancy),
        "average_holding_days": float(avg_holding),
        "median_holding_days": float(median_holding),
    }


def _write_closed_trades_csv(closed: list[ClosedTrade], path: Path) -> None:
    fields = [
        "code", "open_date", "close_date", "quantity",
        "buy_price", "sell_price", "gross_pnl", "gross_return", "holding_days",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for c in closed:
            w.writerow([
                c.code, c.open_date, c.close_date, c.quantity,
                f"{c.buy_price:.6f}", f"{c.sell_price:.6f}",
                f"{c.gross_pnl:.6f}", f"{c.gross_return:.6f}", c.holding_days,
            ])


# ---------------------------------------------------------------------------
# Open position metrics
# ---------------------------------------------------------------------------
def _open_position_metrics(manifest: dict) -> dict:
    ending = manifest.get("ending_positions") or {}
    if not ending:
        return {
            "number_of_open_positions": 0,
            "open_positions_value": 0.0,
            "note": "No open positions at end of run.",
        }
    total_value = 0.0
    for code, pos in ending.items():
        if isinstance(pos, dict):
            v = pos.get("value", 0.0)
        else:
            v = 0.0
        try:
            total_value += float(v)
        except Exception:
            pass
    return {
        "number_of_open_positions": len(ending),
        "open_positions_value": float(total_value),
        "note": "Open positions are excluded from closed-trade win rate. "
                "Unrealized P&L is not computed (would require market data).",
    }


# ---------------------------------------------------------------------------
# Execution quality
# ---------------------------------------------------------------------------
def _execution_quality(manifest: dict) -> dict:
    orders = manifest.get("orders", {}) or {}
    submitted = int(orders.get("submitted", 0) or 0)
    filled = int(orders.get("filled", 0) or 0)
    rejected = int(orders.get("rejected", 0) or 0)
    fill_rate = filled / submitted if submitted > 0 else None
    return {
        "orders_submitted": submitted,
        "orders_filled": filled,
        "orders_rejected": rejected,
        "fill_rate": float(fill_rate) if fill_rate is not None else None,
        "rejection_reasons": manifest.get("rejection_reasons", {}) or {},
    }


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------
def generate_report(run_dir: str | Path) -> dict:
    """Generate the three report files in ``run_dir`` and return the report dict."""
    run_dir = Path(run_dir)
    equity = _load_equity(run_dir)
    trades = _load_trades(run_dir)
    manifest = _load_manifest(run_dir)

    notes: list[str] = []
    initial_cash = float(manifest.get("initial_cash", 0) or 0)

    # Equity metrics
    eq_metrics = _equity_metrics(equity)
    trading_days = eq_metrics.get("trading_days", 0) or 0

    # Trade flow metrics (then patch annualized turnover)
    tf_metrics = _trade_flow_metrics(trades, initial_cash)
    gross_value = tf_metrics.pop("_gross_value", 0.0)
    if initial_cash > 0 and trading_days > 0:
        tf_metrics["annualized_gross_turnover"] = (gross_value / initial_cash) * (TRADING_DAYS_PER_YEAR / trading_days)
    else:
        tf_metrics["annualized_gross_turnover"] = None

    # Closed trades
    closed = _build_closed_trades(trades)
    ct_metrics = _closed_trade_metrics(closed)
    _write_closed_trades_csv(closed, run_dir / "closed_trades.csv")

    # Open positions
    op_metrics = _open_position_metrics(manifest)

    # Execution quality
    exec_metrics = _execution_quality(manifest)

    # Notes
    if trades is None:
        notes.append("trades.csv missing; trade flow and closed-trade metrics are zero/null.")
    elif trades.empty:
        notes.append("trades.csv is empty; trade flow and closed-trade metrics are zero/null.")
    if equity is None:
        notes.append("equity.csv missing; equity metrics are null.")
    if not manifest:
        notes.append("manifest.json missing; execution quality and open positions are null.")
    if not closed:
        notes.append("No closed trades (FIFO produced zero closed lots); closed-trade metrics are null.")
    notes.append("Closed-trade P&L is GROSS (excludes commission/tax). trades.csv has commission/tax columns but they are not netted here per spec §6.3.")
    notes.append(f"risk_free_rate = {RISK_FREE_RATE}; trading_days_per_year = {TRADING_DAYS_PER_YEAR}.")
    if initial_cash > 0:
        notes.append(f"Turnover denominator = manifest.initial_cash = {initial_cash:.2f} (not equity first value).")

    report = {
        "tag": manifest.get("tag", run_dir.name),
        "engine_mode": manifest.get("engine_mode"),
        "start_date": manifest.get("start_date"),
        "end_date": manifest.get("end_date"),
        "initial_cash": initial_cash if initial_cash > 0 else None,
        "equity_metrics": eq_metrics,
        "trade_flow_metrics": tf_metrics,
        "closed_trade_metrics": ct_metrics,
        "open_position_metrics": op_metrics,
        "execution_quality": exec_metrics,
        "notes": notes,
    }

    # Write JSON
    (run_dir / "performance_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Write summary.md
    _write_summary_md(run_dir / "summary.md", report)

    return report


def _fmt_pct(x: Any, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{float(x) * 100:.{digits}f}%"
    except Exception:
        return "n/a"


def _fmt_num(x: Any, digits: int = 4) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return "n/a"


def _write_summary_md(path: Path, r: dict) -> None:
    eq = r.get("equity_metrics", {}) or {}
    tf = r.get("trade_flow_metrics", {}) or {}
    ct = r.get("closed_trade_metrics", {}) or {}
    op = r.get("open_position_metrics", {}) or {}
    ex = r.get("execution_quality", {}) or {}

    lines = [
        f"# Performance Summary - {r.get('tag', '(no tag)')}",
        "",
        f"- Engine mode: `{r.get('engine_mode')}`",
        f"- Window: {r.get('start_date')} -> {r.get('end_date')}",
        f"- Trading days: {eq.get('trading_days', 0)}",
        f"- Initial cash: {r.get('initial_cash')}",
        "",
        "## Equity Metrics",
        "",
        f"- Initial value: {_fmt_num(eq.get('initial_value'), 2)}",
        f"- Ending value: {_fmt_num(eq.get('ending_value'), 2)}",
        f"- Total return: {_fmt_pct(eq.get('total_return'))}",
        f"- Annual return (CAGR): {_fmt_pct(eq.get('annual_return_cagr'))}",
        f"- Volatility (annualized): {_fmt_pct(eq.get('volatility_annualized'))}",
        f"- Sharpe (annualized): {_fmt_num(eq.get('sharpe_annualized'))}",
        f"- Max drawdown: {_fmt_pct(eq.get('max_drawdown'))}",
        f"  - Start: {eq.get('max_drawdown_start')}",
        f"  - End:   {eq.get('max_drawdown_end')}",
        f"- Calmar: {_fmt_num(eq.get('calmar'))}",
        "",
        "## Trade Flow Metrics",
        "",
        f"- Number of fills: {tf.get('number_of_fills', 0)}",
        f"  - Buy fills:  {tf.get('number_of_buy_fills', 0)}",
        f"  - Sell fills: {tf.get('number_of_sell_fills', 0)}",
        f"- Buy turnover:  {_fmt_pct(tf.get('buy_turnover'))}",
        f"- Sell turnover: {_fmt_pct(tf.get('sell_turnover'))}",
        f"- Gross turnover: {_fmt_pct(tf.get('gross_turnover'))}",
        f"- Annualized gross turnover: {_fmt_pct(tf.get('annualized_gross_turnover'))}",
        "",
        "## Closed Trade Metrics (FIFO, gross of costs)",
        "",
        f"- Number of closed trades: {ct.get('number_of_closed_trades', 0)}",
        f"- Win rate: {_fmt_pct(ct.get('win_rate'))}",
        f"- Average return: {_fmt_pct(ct.get('average_return'))}",
        f"- Median return:  {_fmt_pct(ct.get('median_return'))}",
        f"- Average win:    {_fmt_pct(ct.get('average_win'))}",
        f"- Average loss:   {_fmt_pct(ct.get('average_loss'))}",
        f"- Profit/loss ratio: {_fmt_num(ct.get('profit_loss_ratio'))}",
        f"- Expectancy per trade: {_fmt_pct(ct.get('expectancy_per_trade'))}",
        f"- Average holding days: {_fmt_num(ct.get('average_holding_days'), 2)}",
        f"- Median holding days:  {_fmt_num(ct.get('median_holding_days'), 2)}",
        "",
        "## Open Position Metrics",
        "",
        f"- Number of open positions: {op.get('number_of_open_positions', 0)}",
        f"- Open positions value: {_fmt_num(op.get('open_positions_value'), 2)}",
        f"- Note: {op.get('note', '')}",
        "",
        "## Execution Quality",
        "",
        f"- Orders submitted: {ex.get('orders_submitted', 0)}",
        f"- Orders filled:    {ex.get('orders_filled', 0)}",
        f"- Orders rejected:  {ex.get('orders_rejected', 0)}",
        f"- Fill rate: {_fmt_pct(ex.get('fill_rate'))}",
        f"- Rejection reasons:",
    ]
    reasons = ex.get("rejection_reasons", {}) or {}
    if reasons:
        for reason, count in reasons.items():
            lines.append(f"    - {reason}: {count}")
    else:
        lines.append("    - (none)")
    lines += [
        "",
        "## Notes",
        "",
    ]
    for n in r.get("notes", []):
        lines.append(f"- {n}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Aggregate summary
# ---------------------------------------------------------------------------
SUMMARY_FIELDS = [
    "tag", "engine_mode", "start_date", "end_date", "trading_days",
    "ending_value", "total_return", "annual_return_cagr",
    "max_drawdown", "max_drawdown_start", "max_drawdown_end",
    "sharpe_annualized", "gross_turnover", "annualized_gross_turnover",
    "number_of_fills", "number_of_closed_trades", "win_rate",
    "average_return", "profit_loss_ratio", "expectancy_per_trade",
    "average_holding_days", "orders_submitted", "orders_filled",
    "orders_rejected", "fill_rate",
]


def _flatten_for_summary(report: dict) -> dict:
    eq = report.get("equity_metrics", {}) or {}
    tf = report.get("trade_flow_metrics", {}) or {}
    ct = report.get("closed_trade_metrics", {}) or {}
    ex = report.get("execution_quality", {}) or {}
    row = {
        "tag": report.get("tag"),
        "engine_mode": report.get("engine_mode"),
        "start_date": report.get("start_date"),
        "end_date": report.get("end_date"),
        "trading_days": eq.get("trading_days"),
        "ending_value": eq.get("ending_value"),
        "total_return": eq.get("total_return"),
        "annual_return_cagr": eq.get("annual_return_cagr"),
        "max_drawdown": eq.get("max_drawdown"),
        "max_drawdown_start": eq.get("max_drawdown_start"),
        "max_drawdown_end": eq.get("max_drawdown_end"),
        "sharpe_annualized": eq.get("sharpe_annualized"),
        "gross_turnover": tf.get("gross_turnover"),
        "annualized_gross_turnover": tf.get("annualized_gross_turnover"),
        "number_of_fills": tf.get("number_of_fills"),
        "number_of_closed_trades": ct.get("number_of_closed_trades"),
        "win_rate": ct.get("win_rate"),
        "average_return": ct.get("average_return"),
        "profit_loss_ratio": ct.get("profit_loss_ratio"),
        "expectancy_per_trade": ct.get("expectancy_per_trade"),
        "average_holding_days": ct.get("average_holding_days"),
        "orders_submitted": ex.get("orders_submitted"),
        "orders_filled": ex.get("orders_filled"),
        "orders_rejected": ex.get("orders_rejected"),
        "fill_rate": ex.get("fill_rate"),
    }
    return row


def generate_summary(runs_root: str | Path, tags: list[str]) -> None:
    """Write runs/TASK_006B_SUMMARY.md and runs/TASK_006B_SUMMARY.csv."""
    runs_root = Path(runs_root)
    rows: list[dict] = []
    for tag in tags:
        run_dir = runs_root / tag
        rep_path = run_dir / "performance_report.json"
        if not rep_path.exists():
            continue
        try:
            rep = json.loads(rep_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append(_flatten_for_summary(rep))

    # CSV
    csv_path = runs_root / "TASK_006B_SUMMARY.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in SUMMARY_FIELDS})

    # MD
    md_path = runs_root / "TASK_006B_SUMMARY.md"
    lines = [
        "# TASK-006B Aggregate Summary",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Runs: {len(rows)}",
        "",
        "| " + " | ".join(SUMMARY_FIELDS) + " |",
        "|" + "---|" * len(SUMMARY_FIELDS),
    ]
    for row in rows:
        cells = []
        for k in SUMMARY_FIELDS:
            v = row.get(k)
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.4f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="TASK-006B performance report generator")
    p.add_argument("--run-dir", help="Single run directory to report on")
    p.add_argument("--runs-root", default=str(Path(__file__).parent / "runs"),
                   help="Root directory containing run subdirectories")
    p.add_argument("--tags", nargs="*", default=[
        "r2_window1_research", "r2_window1_jq_parity",
        "r2_window2_research", "r2_window2_jq_parity",
        "r2_window3_research", "r2_window3_jq_parity",
        "r2_missing_202606_research",
    ], help="Run tags to include in aggregate summary")
    args = p.parse_args()

    if args.run_dir:
        rep = generate_report(args.run_dir)
        print(f"Report generated for {args.run_dir}: tag={rep.get('tag')}")
    else:
        runs_root = Path(args.runs_root)
        for tag in args.tags:
            run_dir = runs_root / tag
            if not run_dir.exists():
                print(f"SKIP (missing): {tag}")
                continue
            rep = generate_report(run_dir)
            print(f"OK: {tag} | "
                  f"trading_days={rep['equity_metrics'].get('trading_days')} | "
                  f"closed_trades={rep['closed_trade_metrics'].get('number_of_closed_trades', 0)} | "
                  f"win_rate={rep['closed_trade_metrics'].get('win_rate')}")
        generate_summary(runs_root, args.tags)
        print(f"Aggregate summary written to {runs_root}/TASK_006B_SUMMARY.{{md,csv}}")
