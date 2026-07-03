#!/usr/bin/env python3
"""
TASK-005 多版本对比报告生成器
==============================

扫描 runs/<tag>/manifest.json，生成对比表（CLI + Markdown + CSV）。

用法：
    python compare_with_baseline.py
    python compare_with_baseline.py --baseline-tag baseline
"""
import argparse, json, csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RUNS_DIR = SCRIPT_DIR / "runs"


def load_all_runs():
    runs = []
    if not RUNS_DIR.exists():
        return runs
    for d in sorted(RUNS_DIR.iterdir()):
        if not d.is_dir():
            continue
        mf = d / "manifest.json"
        if not mf.exists():
            continue
        with open(mf, "r", encoding="utf-8") as f:
            runs.append(json.load(f))
    return runs


def fmt_pct(x):
    if x is None:
        return "—"
    return f"{x*100:.2f}%"


def fmt_num(x, digits=2):
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def generate_table(runs, baseline_tag="baseline"):
    """生成对比表，basleine 在首行。"""
    baseline = next((r for r in runs if r["tag"] == baseline_tag), None)
    others = [r for r in runs if r["tag"] != baseline_tag]

    headers = [
        "tag", "n_fills", "ending_value", "total_return", "annual_return",
        "sharpe", "max_drawdown", "max_dd_days", "volatility", "calmar",
        "annual_turnover", "win_rate", "trading_days",
    ]

    rows = []
    if baseline:
        rows.append(baseline)
    rows.extend(others)

    # 计算相对 baseline 的 delta（仅数值指标）
    delta_keys = ["n_fills", "ending_value", "total_return", "annual_return",
                  "sharpe", "max_drawdown", "calmar", "annual_turnover", "win_rate"]

    lines = []
    # 表头
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for r in rows:
        m = r.get("metrics", {})
        cells = [
            r["tag"],
            str(m.get("n_fills", "")),
            fmt_num(m.get("ending_value"), 0),
            fmt_pct(m.get("total_return")),
            fmt_pct(m.get("annual_return")),
            fmt_num(m.get("sharpe")),
            fmt_pct(m.get("max_drawdown")),
            str(m.get("max_dd_duration_days", "")),
            fmt_pct(m.get("volatility")),
            fmt_num(m.get("calmar")),
            fmt_num(m.get("annual_turnover"), 2) + "x",
            fmt_pct(m.get("win_rate")),
            str(m.get("trading_days", "")),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    # Delta 表
    if baseline:
        bm = baseline.get("metrics", {})
        lines.append("")
        lines.append("### Delta vs baseline (%s)" % baseline_tag)
        lines.append("")
        delta_headers = ["tag"] + delta_keys
        lines.append("| " + " | ".join(delta_headers) + " |")
        lines.append("|" + "|".join(["---"] * len(delta_headers)) + "|")
        for r in rows:
            m = r.get("metrics", {})
            cells = [r["tag"]]
            for k in delta_keys:
                bv = bm.get(k)
                cv = m.get(k)
                if bv is None or cv is None:
                    cells.append("—")
                else:
                    d = cv - bv
                    if k in ("total_return", "annual_return", "max_drawdown",
                             "annual_turnover", "win_rate"):
                        cells.append(f"{d*100:+.2f}pp")
                    elif k == "ending_value":
                        cells.append(f"{d:+.0f}")
                    else:
                        cells.append(f"{d:+.3f}")
            lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-tag", default="baseline")
    p.add_argument("--output-md", default="comparison_report.md")
    p.add_argument("--output-csv", default="comparison_report.csv")
    args = p.parse_args()

    runs = load_all_runs()
    if not runs:
        print("No runs found in %s" % RUNS_DIR)
        return

    print("=" * 80)
    print("TASK-005 Optimization Comparison Report")
    print("=" * 80)
    table = generate_table(runs, args.baseline_tag)
    print("\n" + table + "\n")

    # 写 Markdown
    out_md = SCRIPT_DIR / args.output_md
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# TASK-005 优化对比报告\n\n")
        f.write("回测区间：2025-01-02 → 2025-12-31，初始资金 100 万元\n\n")
        f.write(table + "\n")
    print("Markdown saved: %s" % out_md)

    # 写 CSV（只导出指标，便于 Excel 分析）
    out_csv = SCRIPT_DIR / args.output_csv
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        headers = ["tag", "n_fills", "ending_value", "total_return", "annual_return",
                   "sharpe", "max_drawdown", "max_dd_duration_days", "volatility",
                   "calmar", "annual_turnover", "win_rate", "trading_days"]
        w.writerow(headers)
        for r in runs:
            m = r.get("metrics", {})
            w.writerow([
                r["tag"],
                m.get("n_fills", ""),
                m.get("ending_value", ""),
                m.get("total_return", ""),
                m.get("annual_return", ""),
                m.get("sharpe", ""),
                m.get("max_drawdown", ""),
                m.get("max_dd_duration_days", ""),
                m.get("volatility", ""),
                m.get("calmar", ""),
                m.get("annual_turnover", ""),
                m.get("win_rate", ""),
                m.get("trading_days", ""),
            ])
    print("CSV saved: %s" % out_csv)


if __name__ == "__main__":
    main()
