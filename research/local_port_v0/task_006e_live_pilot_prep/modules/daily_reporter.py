#!/usr/bin/env python3
"""TASK-006E Stage E5: Daily Reporter Module (degraded mode).

Integrates E2 (signals), E3 (capacity), E4 (risk) outputs into daily pilot
reports and a cross-day dashboard.

This is the DEGRADED MODE implementation (path D):
- Uses historical backtest outputs
- Validates reporting pipeline only

Inputs:
  - reports/daily_signal_YYYYMMDD.csv (E2)
  - reports/daily_execution_feasibility_YYYYMMDD.csv (E3)
  - reports/daily_risk_status_YYYYMMDD.csv (E4)

Outputs:
  - reports/daily_pilot_report_YYYYMMDD.md (human-readable daily report)
  - reports/pilot_dashboard.csv (cross-day summary dashboard)
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "reports"


def load_csv(path: Path) -> list[dict[str, Any]]:
    """Load a CSV file, return list of dicts."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def generate_daily_report(
    date_str: str,
    signals: list[dict],
    feasibility: list[dict],
    risk: dict | None,
) -> str:
    """Generate human-readable daily pilot report markdown."""
    lines = [
        f"# Daily Pilot Report — {date_str}",
        "",
        f"**生成时间**：2026-07-05 (degraded mode replay)",
        f"**模式**：降级方案（T+1 历史回放）",
        "",
        "---",
        "",
    ]

    # Section 1: Signal Summary
    buy_count = sum(1 for s in signals if s.get("action") == "buy")
    sell_count = sum(1 for s in signals if s.get("action") == "sell")
    skip_count = sum(1 for s in signals if s.get("action") == "skip")

    lines.extend([
        "## 1. 今天有没有信号？",
        "",
        f"**有**，共 {len(signals)} 笔信号。" if signals else "**无**，今日无信号。",
        "",
        "| 类型 | 数量 |",
        "|------|-----:|",
        f"| 买入 (buy) | {buy_count} |",
        f"| 卖出 (sell) | {sell_count} |",
        f"| 放弃 (skip) | {skip_count} |",
        "",
    ])

    # Section 2: Theoretical buy/sell list
    lines.extend([
        "## 2. 理论上应该买卖什么？",
        "",
    ])
    if signals:
        lines.extend([
        "| 代码 | 方向 | 目标数量 | 价格 | 原因 |",
        "|------|------|--------:|-----:|------|",
        ])
        for s in signals[:20]:  # limit to first 20
            lines.append(
                f"| {s.get('code', '')} | {s.get('action', '')} | "
                f"{s.get('target_qty', '')} | {s.get('price', '')} | "
                f"{s.get('reason', '')} |"
            )
        if len(signals) > 20:
            lines.append(f"| ... | ... | ... | ... | (共 {len(signals)} 笔，仅显示前 20) |")
        lines.append("")

    # Section 3: Execution feasibility
    lines.extend([
        "## 3. 实盘是否可执行？",
        "",
    ])
    if feasibility:
        exec_count = sum(1 for f in feasibility if f.get("executable") == "Y")
        rej_count = len(feasibility) - exec_count
        lines.extend([
            f"**可执行**：{exec_count} 笔",
            f"**拒绝**：{rej_count} 笔",
            "",
            "| 代码 | 方向 | 竞价量 | 参与率 | 可执行 | 拒绝原因 |",
            "|------|------|-------:|-------:|--------|----------|",
        ])
        for f in feasibility[:20]:
            lines.append(
                f"| {f.get('code', '')} | {f.get('side', '')} | "
                f"{f.get('auction_volume_0925', '')} | "
                f"{f.get('participation_rate', '')} | "
                f"{f.get('executable', '')} | {f.get('rejection_reason', '')} |"
            )
        if len(feasibility) > 20:
            lines.append(f"| ... | ... | ... | ... | ... | (共 {len(feasibility)} 笔) |")
        lines.append("")

    # Section 4: Rejected orders
    lines.extend([
        "## 4. 哪些票因为容量/涨跌停/停牌放弃？",
        "",
    ])
    rejected = [f for f in feasibility if f.get("executable") == "N"]
    if rejected:
        lines.extend([
        "| 代码 | 方向 | 拒绝原因 |",
        "|------|------|----------|",
        ])
        for r in rejected[:20]:
            lines.append(f"| {r.get('code', '')} | {r.get('side', '')} | {r.get('rejection_reason', '')} |")
        lines.append("")

    # Section 5: Risk status
    lines.extend([
        "## 5. 今天是否触发警戒？",
        "",
    ])
    if risk:
        status = risk.get("risk_status", "UNKNOWN")
        alerts = risk.get("alerts", "")
        if status == "WARNING":
            lines.append(f"**是**，触发 WARNING：{alerts}")
        elif status == "HALTED":
            lines.append(f"**是**，触发 HALTED：{alerts}")
        else:
            lines.append("**否**，风控状态正常（NORMAL）")
        lines.extend([
            "",
            "| 指标 | 值 |",
            "|------|-----:|",
            f"| 累计回撤 | {risk.get('cumulative_drawdown', '')} |",
            f"| 20日滚动收益 | {risk.get('rolling_20d_return', '')} |",
            f"| 20日滚动胜率 | {risk.get('rolling_20d_winrate', '')} |",
            f"| 连续亏损天数 | {risk.get('consecutive_losses', '')} |",
            f"| 订单拒绝率 | {risk.get('rejection_rate', '')} |",
            "",
        ])
    else:
        lines.append("**无数据**（风控状态未生成）")
        lines.append("")

    # Section 6: Halt check
    lines.extend([
        "## 6. 今天是否触发停机？",
        "",
    ])
    if risk:
        status = risk.get("risk_status", "UNKNOWN")
        if status == "HALTED":
            lines.append("**是**，已触发停机。**严禁继续提交订单**。")
        else:
            lines.append("**否**，未触发停机。")
    else:
        lines.append("**无数据**")
    lines.append("")

    # Section 7: Action tomorrow
    lines.extend([
        "## 7. 是否允许明天继续观察？",
        "",
    ])
    if risk:
        status = risk.get("risk_status", "UNKNOWN")
        if status == "HALTED":
            lines.append("**否**，已停机，需人工确认后进入 RECOVERY。")
            action = "halt"
        elif status == "WARNING":
            lines.append("**是**，但需密切监控（WARNING 状态）。")
            action = "warn"
        else:
            lines.append("**是**，风控正常，可继续观察。")
            action = "continue"
    else:
        lines.append("**未知**（风控数据缺失）")
        action = "unknown"
    lines.append("")

    return "\n".join(lines), action


def generate_dashboard_row(
    date_str: str,
    signals: list[dict],
    feasibility: list[dict],
    risk: dict | None,
) -> dict:
    """Generate a single dashboard row for the date."""
    buy_count = sum(1 for s in signals if s.get("action") == "buy")
    sell_count = sum(1 for s in signals if s.get("action") == "sell")
    skip_count = sum(1 for s in signals if s.get("action") == "skip")

    exec_count = sum(1 for f in feasibility if f.get("executable") == "Y")
    rej_count = len(feasibility) - exec_count

    if risk:
        risk_status = risk.get("risk_status", "UNKNOWN")
        cum_dd = risk.get("cumulative_drawdown", "")
        rolling_ret = risk.get("rolling_20d_return", "")
        rolling_wr = risk.get("rolling_20d_winrate", "")
        consec = risk.get("consecutive_losses", "")
        rej_rate = risk.get("rejection_rate", "")

        if risk_status == "HALTED":
            action = "halt"
        elif risk_status == "WARNING":
            action = "warn"
        else:
            action = "continue"
    else:
        risk_status = "NO_DATA"
        cum_dd = rolling_ret = rolling_wr = consec = rej_rate = ""
        action = "unknown"

    return {
        "date": date_str,
        "signals_count": len(signals),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "skip_count": skip_count,
        "executable_count": exec_count,
        "rejected_count": rej_count,
        "risk_status": risk_status,
        "cumulative_drawdown": cum_dd,
        "rolling_20d_return": rolling_ret,
        "rolling_20d_winrate": rolling_wr,
        "consecutive_losses": consec,
        "rejection_rate": rej_rate,
        "action_tomorrow": action,
    }


def main() -> None:
    print("=" * 70)
    print("TASK-006E Stage E5: Daily Reporter (degraded mode)")
    print("=" * 70)

    # Find all signal files to determine date range
    signal_files = sorted(OUTPUT_DIR.glob("daily_signal_*.csv"))
    signal_files = [f for f in signal_files if "summary" not in f.name]
    print(f"\n[1] Found {len(signal_files)} signal files")

    # Also get risk status files (1549 days, more than signal files)
    risk_files = sorted(OUTPUT_DIR.glob("daily_risk_status_*.csv"))
    print(f"  Found {len(risk_files)} risk status files")

    # Build complete date set (union of signal dates and risk dates)
    all_dates = set()
    for f in signal_files:
        date_compact = f.stem.replace("daily_signal_", "")
        all_dates.add(f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}")
    for f in risk_files:
        date_compact = f.stem.replace("daily_risk_status_", "")
        all_dates.add(f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}")

    print(f"  Total unique dates: {len(all_dates)}")

    print("\n[2] Generating daily reports and dashboard...")
    dashboard_rows = []
    reports_generated = 0

    for date_str in sorted(all_dates):
        date_compact = date_str.replace("-", "")

        # Load E2 signals
        signal_path = OUTPUT_DIR / f"daily_signal_{date_compact}.csv"
        signals = load_csv(signal_path)

        # Load E3 feasibility
        feas_path = OUTPUT_DIR / f"daily_execution_feasibility_{date_compact}.csv"
        feasibility = load_csv(feas_path)

        # Load E4 risk status
        risk_path = OUTPUT_DIR / f"daily_risk_status_{date_compact}.csv"
        risk_rows = load_csv(risk_path)
        risk = risk_rows[0] if risk_rows else None

        # Generate daily report
        report_md, action = generate_daily_report(date_str, signals, feasibility, risk)
        report_path = OUTPUT_DIR / f"daily_pilot_report_{date_compact}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        reports_generated += 1

        # Generate dashboard row
        row = generate_dashboard_row(date_str, signals, feasibility, risk)
        dashboard_rows.append(row)

    print(f"  Generated {reports_generated} daily reports")

    # Write dashboard
    print("\n[3] Writing pilot dashboard...")
    dashboard_path = OUTPUT_DIR / "pilot_dashboard.csv"
    if dashboard_rows:
        fields = list(dashboard_rows[0].keys())
        with open(dashboard_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in dashboard_rows:
                writer.writerow(row)
        print(f"  -> {dashboard_path}")
        print(f"  Dashboard rows: {len(dashboard_rows)}")

    # Summary stats
    print("\n[4] Dashboard summary:")
    from collections import Counter
    status_counter = Counter(r["risk_status"] for r in dashboard_rows)
    action_counter = Counter(r["action_tomorrow"] for r in dashboard_rows)
    print("  Risk status distribution:")
    for s, c in sorted(status_counter.items()):
        print(f"    {s}: {c}")
    print("  Action tomorrow distribution:")
    for a, c in sorted(action_counter.items()):
        print(f"    {a}: {c}")

    print("\n[E5] Done.")


if __name__ == "__main__":
    main()
