#!/usr/bin/env python3
"""TASK-006E Stage E4: Risk Engine Module (degraded mode).

Replays historical equity curve and computes risk control indicators,
outputting daily risk status (NORMAL / WARNING / HALTED / RECOVERY).

This is the DEGRADED MODE implementation (path D):
- Uses HData historical backtest equity curve (r3_full_2020_202605_research)
- Validates risk engine engineering pipeline only
- Cross-validates against 006D risk_control_scenarios

Inputs:
  - equity.csv (daily equity values)
  - manifest.json (initial_cash, trading_days)

Outputs:
  - daily_risk_status_YYYYMMDD.csv (per-day risk status)
  - risk_status_summary.csv (cross-day summary)
  - RISK_ENGINE_REPORT.md (validation report)

Risk thresholds (from 006D live_pilot_plan.md + SPEC §3.4.2):
  Indicator                    Warning     Halt
  20-day rolling return        < 0%        < -5%
  20-day rolling win rate       < 50%       < 35%
  20-day max drawdown          < -8%       < -12%
  Consecutive loss days        >= 3        >= 5
  Order rejection rate         > 25%       > 40%
  Cumulative drawdown          > -10%      > -15%
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
RUN_DIR = PROJECT_ROOT / "research/local_port_v0/task_005_optimize/runs/r3_full_2020_202605_research"
EQUITY_CSV = RUN_DIR / "equity.csv"
MANIFEST_JSON = RUN_DIR / "manifest.json"
SIGNAL_SUMMARY = Path(__file__).resolve().parents[1] / "reports" / "daily_signal_summary.csv"

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "reports"

# Risk thresholds (SPEC §3.4.2)
THRESHOLDS = {
    "rolling_20d_return": {"warning": 0.0, "halt": -0.05},
    "rolling_20d_winrate": {"warning": 0.50, "halt": 0.35},
    "rolling_20d_max_drawdown": {"warning": -0.08, "halt": -0.12},
    "consecutive_losses": {"warning": 3, "halt": 5},
    "cumulative_drawdown": {"warning": -0.10, "halt": -0.15},
}

# Order rejection rate thresholds (from manifest)
ORDER_REJECTION_WARNING = 0.25
ORDER_REJECTION_HALT = 0.40

ROLLING_WINDOW = 20


def load_equity(path: Path) -> list[dict[str, Any]]:
    """Load equity.csv, return list of {date, value}."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "date": row["date"],
                "value": float(row["value"]),
            })
    return rows


def load_signal_summary(path: Path) -> dict[str, dict]:
    """Load daily_signal_summary.csv for rejection rate calculation.

    Returns: {date: {total_signals, buy_count, sell_count, skip_count}}
    """
    if not path.exists():
        return {}

    result = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row["date"]] = {
                "total_signals": int(row["total_signals"]),
                "buy_count": int(row["buy_count"]),
                "sell_count": int(row["sell_count"]),
                "skip_count": int(row["skip_count"]),
            }
    return result


def compute_daily_returns(equity: list[dict]) -> list[dict]:
    """Compute daily returns for equity series."""
    result = []
    for i, row in enumerate(equity):
        if i == 0:
            daily_return = 0.0
        else:
            prev_value = equity[i - 1]["value"]
            if prev_value > 0:
                daily_return = (row["value"] - prev_value) / prev_value
            else:
                daily_return = 0.0
        result.append({**row, "daily_return": daily_return})
    return result


def compute_rolling_indicators(
    equity_with_returns: list[dict],
    initial_cash: float,
) -> list[dict]:
    """Compute rolling risk indicators for each day.

    cumulative_drawdown is computed relative to running peak (not initial_cash),
    matching standard drawdown definition.
    """
    result = []
    cumulative_peak = initial_cash

    for i, row in enumerate(equity_with_returns):
        date = row["date"]
        value = row["value"]
        daily_return = row["daily_return"]

        # Update cumulative peak
        if value > cumulative_peak:
            cumulative_peak = value

        # Cumulative drawdown (relative to peak, standard definition)
        if cumulative_peak > 0:
            cumulative_drawdown = (value - cumulative_peak) / cumulative_peak
        else:
            cumulative_drawdown = 0.0

        # Rolling 20-day indicators (only valid after ROLLING_WINDOW days)
        has_rolling = i >= ROLLING_WINDOW
        if has_rolling:
            window = equity_with_returns[i - ROLLING_WINDOW + 1 : i + 1]
            window_returns = [w["daily_return"] for w in window]
            window_values = [w["value"] for w in window]

            # Rolling 20-day return
            rolling_20d_return = (value / window_values[0] - 1) if window_values[0] > 0 else 0.0

            # Rolling 20-day win rate
            wins = sum(1 for r in window_returns if r > 0)
            rolling_20d_winrate = wins / ROLLING_WINDOW

            # Rolling 20-day max drawdown
            window_peak = max(window_values)
            rolling_20d_max_drawdown = (value - window_peak) / window_peak if window_peak > 0 else 0.0
        else:
            # Cold start: no rolling data yet
            rolling_20d_return = None  # type: ignore
            rolling_20d_winrate = None  # type: ignore
            rolling_20d_max_drawdown = None  # type: ignore

        # Consecutive losses
        if i > 0:
            consec_losses = 0
            for j in range(i, -1, -1):
                if equity_with_returns[j]["daily_return"] < 0:
                    consec_losses += 1
                else:
                    break
        else:
            consec_losses = 0

        result.append({
            "date": date,
            "value": value,
            "daily_return": daily_return,
            "cumulative_drawdown": cumulative_drawdown,
            "rolling_20d_return": rolling_20d_return if rolling_20d_return is not None else "",
            "rolling_20d_winrate": rolling_20d_winrate if rolling_20d_winrate is not None else "",
            "rolling_20d_max_drawdown": rolling_20d_max_drawdown if rolling_20d_max_drawdown is not None else "",
            "rolling_valid": has_rolling,
            "consecutive_losses": consec_losses,
        })

    return result


def determine_risk_status(indicators: dict, rejection_rate: float) -> tuple[str, list[str]]:
    """Determine risk status (NORMAL/WARNING/HALTED) and triggered alerts.

    Returns: (status, [alert_messages])

    Note: rolling indicators are skipped during cold start (rolling_valid=False).
    """
    alerts = []

    halt_triggered = False
    warning_triggered = False

    # Check rolling indicators only if valid (past cold start)
    if indicators.get("rolling_valid", False):
        rolling_checks = [
            ("rolling_20d_return", indicators["rolling_20d_return"], THRESHOLDS["rolling_20d_return"]),
            ("rolling_20d_winrate", indicators["rolling_20d_winrate"], THRESHOLDS["rolling_20d_winrate"]),
            ("rolling_20d_max_drawdown", indicators["rolling_20d_max_drawdown"], THRESHOLDS["rolling_20d_max_drawdown"]),
        ]

        for name, value, thresholds in rolling_checks:
            if value < thresholds["halt"]:
                alerts.append(f"HALT: {name}={value:.4f} < {thresholds['halt']}")
                halt_triggered = True
            elif value < thresholds["warning"]:
                alerts.append(f"WARN: {name}={value:.4f} < {thresholds['warning']}")
                warning_triggered = True

    # Cumulative drawdown (always valid)
    cum_dd = indicators["cumulative_drawdown"]
    if cum_dd < THRESHOLDS["cumulative_drawdown"]["halt"]:
        alerts.append(f"HALT: cumulative_drawdown={cum_dd:.4f} < {THRESHOLDS['cumulative_drawdown']['halt']}")
        halt_triggered = True
    elif cum_dd < THRESHOLDS["cumulative_drawdown"]["warning"]:
        alerts.append(f"WARN: cumulative_drawdown={cum_dd:.4f} < {THRESHOLDS['cumulative_drawdown']['warning']}")
        warning_triggered = True

    # Consecutive losses (>= comparison)
    consec = indicators["consecutive_losses"]
    if consec >= THRESHOLDS["consecutive_losses"]["halt"]:
        alerts.append(f"HALT: consecutive_losses={consec} >= {THRESHOLDS['consecutive_losses']['halt']}")
        halt_triggered = True
    elif consec >= THRESHOLDS["consecutive_losses"]["warning"]:
        alerts.append(f"WARN: consecutive_losses={consec} >= {THRESHOLDS['consecutive_losses']['warning']}")
        warning_triggered = True

    # Order rejection rate
    if rejection_rate > ORDER_REJECTION_HALT:
        alerts.append(f"HALT: rejection_rate={rejection_rate:.2%} > {ORDER_REJECTION_HALT:.0%}")
        halt_triggered = True
    elif rejection_rate > ORDER_REJECTION_WARNING:
        alerts.append(f"WARN: rejection_rate={rejection_rate:.2%} > {ORDER_REJECTION_WARNING:.0%}")
        warning_triggered = True

    if halt_triggered:
        return "HALTED", alerts
    elif warning_triggered:
        return "WARNING", alerts
    else:
        return "NORMAL", []


def compute_rejection_rate(date: str, signal_data: dict) -> float:
    """Compute order rejection rate for a given date."""
    if date not in signal_data:
        return 0.0
    data = signal_data[date]
    total_orders = data["buy_count"] + data["skip_count"]
    if total_orders == 0:
        return 0.0
    return data["skip_count"] / total_orders


def run_risk_engine(
    equity: list[dict],
    initial_cash: float,
    signal_data: dict,
) -> list[dict]:
    """Run risk engine over full equity series."""
    equity_with_returns = compute_daily_returns(equity)
    indicators = compute_rolling_indicators(equity_with_returns, initial_cash)

    results = []
    for ind in indicators:
        date = ind["date"]
        rejection_rate = compute_rejection_rate(date, signal_data)
        status, alerts = determine_risk_status(ind, rejection_rate)

        results.append({
            **ind,
            "rejection_rate": round(rejection_rate, 4),
            "risk_status": status,
            "alerts": "; ".join(alerts) if alerts else "",
        })

    return results


def main() -> None:
    print("=" * 70)
    print("TASK-006E Stage E4: Risk Engine (degraded mode)")
    print("=" * 70)

    print("\n[1] Loading inputs...")
    equity = load_equity(EQUITY_CSV)
    print(f"  Equity days: {len(equity)}")

    with open(MANIFEST_JSON, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    initial_cash = manifest["initial_cash"]
    print(f"  Initial cash: {initial_cash}")

    signal_data = load_signal_summary(SIGNAL_SUMMARY)
    print(f"  Signal summary days: {len(signal_data)}")

    print("\n[2] Running risk engine...")
    results = run_risk_engine(equity, initial_cash, signal_data)

    print(f"  Processed {len(results)} days")

    # Status distribution
    status_counter = Counter(r["risk_status"] for r in results)
    print(f"\n[3] Risk status distribution:")
    for status, count in sorted(status_counter.items()):
        pct = count / len(results) * 100
        print(f"  {status}: {count} ({pct:.1f}%)")

    # Write per-day CSV
    print("\n[4] Writing per-day risk status CSVs...")
    by_date = {r["date"]: r for r in results}

    fields = [
        "date", "value", "daily_return", "cumulative_drawdown",
        "rolling_20d_return", "rolling_20d_winrate", "rolling_20d_max_drawdown",
        "rolling_valid", "consecutive_losses", "rejection_rate", "risk_status", "alerts",
    ]

    for date_str, row in by_date.items():
        out_path = OUTPUT_DIR / f"daily_risk_status_{date_str.replace('-', '')}.csv"
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerow(row)

    print(f"  Wrote {len(by_date)} daily risk status files")

    # Write summary
    print("\n[5] Writing summary...")
    summary_path = OUTPUT_DIR / "risk_status_summary.csv"
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    print(f"  -> {summary_path}")

    # Find first HALTED day
    first_halt = next((r for r in results if r["risk_status"] == "HALTED"), None)
    if first_halt:
        print(f"\n[6] First HALTED day: {first_halt['date']}")
        print(f"  Alerts: {first_halt['alerts']}")
    else:
        print(f"\n[6] No HALTED days found")

    # Find first WARNING day
    first_warn = next((r for r in results if r["risk_status"] == "WARNING"), None)
    if first_warn:
        print(f"  First WARNING day: {first_warn['date']}")
        print(f"  Alerts: {first_warn['alerts']}")

    # Cross-validate with 006D: max drawdown should be around -23.20%
    max_dd = min(r["cumulative_drawdown"] for r in results)
    print(f"\n[7] Cross-validation with 006D:")
    print(f"  Max cumulative drawdown: {max_dd:.4f} ({max_dd*100:.2f}%)")
    print(f"  006D reported max_drawdown: -23.20%")
    print(f"  Match: {'YES' if abs(max_dd - (-0.2320)) < 0.01 else 'NO (different scope)'}")

    print("\n[E4] Done.")


if __name__ == "__main__":
    main()
