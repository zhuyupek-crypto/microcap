"""
TASK-005 参数敏感性测试：stocknum × phase_cycle 网格扫描
=======================================================

测试维度：
    - stocknum: [5, 10, 20]  （持股数量）
    - phase_cycle: [10, 15, 30]  （批次周期）
    - min_list_days: 固定 375

共 9 个组合，每个跑 2025 年回测。
基线：stocknum=10, phase_cycle=15（P3_code_cleanup 的默认值）

使用方法：
    python param_sensitivity.py
"""
import os
import subprocess
import json
import sys

TASK_ROOT = r"d:\Work Space\他山之石\微盘股\research\local_port_v0\task_005_optimize"
STRATEGY_TEMPLATE = os.path.join(TASK_ROOT, "strategies", "P3_code_cleanup.py")
OUTPUT_DIR = os.path.join(TASK_ROOT, "runs")
SENSITIVITY_DIR = os.path.join(TASK_ROOT, "strategies", "sensitivity")

PARAM_GRID = [
    {"stocknum": 5, "phase_cycle": 10},
    {"stocknum": 5, "phase_cycle": 15},
    {"stocknum": 5, "phase_cycle": 30},
    {"stocknum": 10, "phase_cycle": 10},
    {"stocknum": 10, "phase_cycle": 15},  # baseline
    {"stocknum": 10, "phase_cycle": 30},
    {"stocknum": 20, "phase_cycle": 10},
    {"stocknum": 20, "phase_cycle": 15},
    {"stocknum": 20, "phase_cycle": 30},
]


def generate_strategy(params):
    """基于 P3_code_cleanup.py 生成参数化策略文件。"""
    with open(STRATEGY_TEMPLATE, "r", encoding="utf-8") as f:
        content = f.read()

    # 替换 stocknum
    content = content.replace(
        "g.stocknum = 10",
        "g.stocknum = %d" % params["stocknum"]
    )
    # 替换 phase_cycle
    content = content.replace(
        "g.phase_cycle = 15",
        "g.phase_cycle = %d" % params["phase_cycle"]
    )

    filename = "sens_s%d_p%d.py" % (params["stocknum"], params["phase_cycle"])
    filepath = os.path.join(SENSITIVITY_DIR, filename)
    os.makedirs(SENSITIVITY_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def run_backtest(strategy_path, tag, start_date="2025-01-02", end_date="2025-12-31"):
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
        print(result.stderr[-500:])
        return None

    manifest_path = os.path.join(OUTPUT_DIR, tag, "manifest.json")
    if not os.path.exists(manifest_path):
        print("No manifest: %s" % tag)
        return None
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    results = []
    for params in PARAM_GRID:
        tag = "sens_s%d_p%d_2025" % (params["stocknum"], params["phase_cycle"])
        strategy_path = generate_strategy(params)
        manifest = run_backtest(strategy_path, tag)
        if manifest:
            metrics = manifest.get("metrics", {})
            results.append({
                "tag": tag,
                "stocknum": params["stocknum"],
                "phase_cycle": params["phase_cycle"],
                "annual_ret": metrics.get("annual_return", 0),
                "sharpe": metrics.get("sharpe", 0),
                "max_dd": metrics.get("max_drawdown", 0),
                "calmar": metrics.get("calmar", 0),
                "volatility": metrics.get("volatility", 0),
                "turnover": metrics.get("annual_turnover", 0),
            })
            print("  => %s: ret=%.2f%% sharpe=%.2f dd=%.2f%%" % (
                tag, results[-1]["annual_ret"] * 100, results[-1]["sharpe"], results[-1]["max_dd"] * 100
            ))

    # 输出汇总
    print("\n" + "=" * 80)
    print("PARAMETER SENSITIVITY RESULTS (2025)")
    print("=" * 80)
    print("%-8s %-8s %-10s %-8s %-10s %-8s %-10s" % (
        "stockN", "cycle", "annual_ret", "sharpe", "max_dd", "calmar", "turnover"))
    print("-" * 80)
    for r in results:
        print("%-8d %-8d %-10.2f%% %-8.2f %-10.2f%% %-8.2f %-10.2f" % (
            r["stocknum"], r["phase_cycle"],
            r["annual_ret"] * 100, r["sharpe"], r["max_dd"] * 100,
            r["calmar"], r["turnover"]))

    # 保存 JSON
    output_json = os.path.join(OUTPUT_DIR, "sensitivity_results.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nResults saved to: %s" % output_json)


if __name__ == "__main__":
    main()
