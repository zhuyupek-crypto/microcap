"""
TASK-005 更长历史回测：2021-2023 年验证（含 2022 熊市）
=======================================================

使用推荐版本 P3_code_cleanup.py 分别跑 2021/2022/2023 三个年度，
获取年度绩效指标，重点观察 2022 年熊市中的回撤与防御机制表现。

使用方法：
    python longer_history_backtest.py
"""
import os
import subprocess
import json
import sys

TASK_ROOT = r"d:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize"
STRATEGY = os.path.join(TASK_ROOT, "strategies", "P3_code_cleanup.py")
OUTPUT_DIR = os.path.join(TASK_ROOT, "runs")

# 三个年度分别回测，便于年度对比
YEAR_GRID = [
    {"year": 2021, "start": "2021-01-04", "end": "2021-12-31"},
    {"year": 2022, "start": "2022-01-04", "end": "2022-12-30"},
    {"year": 2023, "start": "2023-01-03", "end": "2023-12-29"},
]


def run_backtest(strategy_path, tag, start_date, end_date):
    """运行回测并返回结果。"""
    cmd = [
        sys.executable, "backtest_runner.py",
        "--strategy", strategy_path,
        "--tag", tag,
        "--start-date", start_date,
        "--end-date", end_date,
    ]
    print("Running: %s" % " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=TASK_ROOT)
    if result.returncode != 0:
        print("FAILED: %s" % tag)
        print(result.stderr[-1000:])
        return None

    manifest_path = os.path.join(OUTPUT_DIR, tag, "manifest.json")
    if not os.path.exists(manifest_path):
        print("No manifest: %s" % tag)
        return None
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    results = []
    for cfg in YEAR_GRID:
        tag = "P3_long_%d" % cfg["year"]
        manifest = run_backtest(STRATEGY, tag, cfg["start"], cfg["end"])
        if manifest:
            metrics = manifest.get("metrics", {})
            results.append({
                "tag": tag,
                "year": cfg["year"],
                "annual_ret": metrics.get("annual_return", 0),
                "sharpe": metrics.get("sharpe", 0),
                "max_dd": metrics.get("max_drawdown", 0),
                "calmar": metrics.get("calmar", 0),
                "volatility": metrics.get("volatility", 0),
                "turnover": metrics.get("annual_turnover", 0),
                "win_rate": metrics.get("win_rate", 0),
                "n_fills": metrics.get("n_fills", 0),
                "ending_value": metrics.get("ending_value", 0),
                "trading_days": metrics.get("trading_days", 0),
            })
            print("  => %s: ret=%.2f%% sharpe=%.2f dd=%.2f%%" % (
                tag, results[-1]["annual_ret"] * 100, results[-1]["sharpe"], results[-1]["max_dd"] * 100
            ))

    # 输出汇总
    print("\n" + "=" * 90)
    print("LONGER HISTORY BACKTEST RESULTS (P3_code_cleanup)")
    print("=" * 90)
    print("%-6s %-10s %-8s %-10s %-8s %-10s %-8s %-8s" % (
        "Year", "annual_ret", "sharpe", "max_dd", "calmar", "volatility", "turnover", "win_rate"))
    print("-" * 90)
    for r in results:
        print("%-6d %-10.2f%% %-8.2f %-10.2f%% %-8.2f %-10.2f%% %-8.2f %-8.2f%%" % (
            r["year"],
            r["annual_ret"] * 100, r["sharpe"], r["max_dd"] * 100,
            r["calmar"], r["volatility"] * 100, r["turnover"], r["win_rate"] * 100))

    # 保存 JSON
    output_json = os.path.join(OUTPUT_DIR, "longer_history_results.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nResults saved to: %s" % output_json)


if __name__ == "__main__":
    main()
